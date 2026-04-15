<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, VaultStats, ContentType } from '$lib/types';

	let stats: VaultStats | null = $state(null);
	let contents: Content[] = $state([]);
	let filter: ContentType | 'all' = $state('all');
	let showAdd = $state(false);
	let loading = $state(true);

	// Add form
	let addTitle = $state('');
	let addType: ContentType = $state('youtube');
	let addUrl = $state('');
	let addDuration = $state(0);
	let addAuthor = $state('');
	let addNotes = $state('');
	let addThumbnail = $state('');
	let addSourceId = $state('');
	let addError = $state('');
	let lookupLoading = $state(false);
	let lastLookupUrl = $state('');
	let autoLookupTimer: ReturnType<typeof setTimeout> | null = null;

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		load();
	});

	async function load() {
		loading = true;
		try {
			[stats, contents] = await Promise.all([
				api.get<VaultStats>('/contents/stats'),
				api.get<Content[]>('/contents?consumed=false')
			]);
		} finally { loading = false; }
	}

	$effect(() => {
		if (!auth.isLoggedIn) return;
		const type = filter;
		const url = type === 'all' ? '/contents?consumed=false' : `/contents?consumed=false&content_type=${type}`;
		api.get<Content[]>(url).then(r => contents = r);
	});

	function isLookupCandidate(url: string): boolean {
		try {
			const parsed = new URL(url);
			return (
				parsed.hostname.includes('youtube.com') ||
				parsed.hostname.includes('youtu.be') ||
				parsed.hostname.includes('store.steampowered.com')
			);
		} catch {
			return false;
		}
	}

	$effect(() => {
		const url = addUrl.trim();
		if (!showAdd || !url || !isLookupCandidate(url) || lookupLoading || url === lastLookupUrl) return;

		if (autoLookupTimer) clearTimeout(autoLookupTimer);
		autoLookupTimer = setTimeout(() => {
			void lookupUrl(url);
		}, 350);

		return () => {
			if (autoLookupTimer) {
				clearTimeout(autoLookupTimer);
				autoLookupTimer = null;
			}
		};
	});

	async function lookupUrl(overrideUrl?: string) {
		const targetUrl = (overrideUrl ?? addUrl).trim();
		if (!targetUrl) return;
		addError = '';
		lookupLoading = true;
		try {
			let endpoint = '';
			if (targetUrl.includes('youtube.com') || targetUrl.includes('youtu.be')) {
				endpoint = `/lookup/youtube?url=${encodeURIComponent(targetUrl)}`;
				addType = 'youtube';
			} else if (targetUrl.includes('store.steampowered.com')) {
				endpoint = `/lookup/steam?url=${encodeURIComponent(targetUrl)}`;
				addType = 'game';
			}
			if (endpoint) {
				const data = await api.get<any>(endpoint);
				addTitle = data.title || addTitle;
				addAuthor = data.author || addAuthor;
				addThumbnail = data.thumbnail || '';
				addSourceId = data.source_id || '';
				if (data.duration_minutes) addDuration = data.duration_minutes;
				lastLookupUrl = targetUrl;
			}
		} catch (e: unknown) {
			addError = e instanceof Error ? e.message : 'Lookup failed';
		} finally { lookupLoading = false; }
	}

	async function submitAdd() {
		addError = '';
		try {
			await api.post('/contents', {
				title: addTitle,
				content_type: addType,
				url: addUrl || null,
				thumbnail: addThumbnail || null,
				duration_minutes: addDuration,
				source_id: addSourceId || null,
				author: addAuthor || null,
				notes: addNotes || null
			});
			showAdd = false;
			resetForm();
			load();
		} catch (e: unknown) {
			addError = e instanceof Error ? e.message : 'Error';
		}
	}

	function resetForm() {
		addTitle = ''; addUrl = ''; addDuration = 0; addAuthor = '';
		addNotes = ''; addThumbnail = ''; addSourceId = ''; addType = 'youtube';
		lastLookupUrl = '';
	}

	async function consume(id: number) {
		await api.post(`/contents/${id}/consume`);
		load();
	}

	async function remove(id: number) {
		await api.del(`/contents/${id}`);
		load();
	}
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}
	<!-- Hero: total pending time -->
	{#if stats}
		<div class="hero-number">
			<div class="number">{formatDuration(stats.total_pending_minutes)}</div>
			<div class="unit">de contenido por consumir</div>
		</div>

		<div class="stat-row">
			<div class="stat-pill">
				<span>📦</span> <span class="val">{stats.pending_count}</span> pendientes
			</div>
			<div class="stat-pill">
				<span>✅</span> <span class="val">{stats.consumed_count}</span> consumidos
			</div>
		</div>

		{#if Object.keys(stats.by_type).length > 0}
			<div class="stat-row">
				{#each Object.entries(stats.by_type) as [type, mins]}
					<div class="stat-pill">
						<span>{TYPE_ICONS[type] || '📄'}</span>
						<span class="val">{formatDuration(mins)}</span>
						{TYPE_LABELS[type] || type}
					</div>
				{/each}
			</div>
		{/if}
	{/if}

	<!-- Filter tabs -->
	<div class="tabs">
		<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️ YouTube</button>
		<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬 Pelis</button>
		<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖 Libros</button>
		<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮 Juegos</button>
	</div>

	<!-- Content list -->
	{#if loading}
		<p style="text-align:center; color:var(--text-muted);">Cargando…</p>
	{:else if contents.length === 0}
		<div class="card" style="text-align:center; padding:2rem;">
			<p style="font-size:1.2rem; margin-bottom:0.5rem;">🏛️</p>
			<p style="color:var(--text-muted);">La bóveda está vacía. ¡Añade contenido!</p>
		</div>
	{:else}
		<div style="display:flex; flex-direction:column; gap:0.5rem;">
			{#each contents as c (c.id)}
				{@const link = buildConsumeUrl(c)}
				<div class="content-card">
					{#if c.thumbnail}
						<img class="thumb" src={c.thumbnail} alt="" />
					{:else}
						<div class="thumb" style="display:flex; align-items:center; justify-content:center; font-size:1.5rem;">
							{TYPE_ICONS[c.content_type] || '📄'}
						</div>
					{/if}
					<div class="info">
						<div class="title">{c.title}</div>
						<div class="meta">
							<span class="badge {c.content_type}">{TYPE_LABELS[c.content_type]}</span>
							{#if c.duration_minutes > 0}
								<span>⏱ {formatDuration(c.duration_minutes)}</span>
							{/if}
							{#if c.author}
								<span>{c.author}</span>
							{/if}
						</div>
						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn-secondary">Abrir</button>
								</a>
							{/if}
							<button onclick={() => consume(c.id)} style="background:rgba(79,255,170,0.15); color:var(--game); box-shadow:none;">✓</button>
							<button class="btn-danger" onclick={() => remove(c.id)}>✕</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- FAB -->
	<button class="fab" onclick={() => showAdd = true}>+</button>

	<!-- Add modal -->
	{#if showAdd}
		<div class="overlay" onclick={() => showAdd = false} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal" onclick={e => e.stopPropagation()} role="dialog">
				<h2>Añadir contenido</h2>

				<div class="form-group">
					<label for="add-url">URL (pega un enlace para autodetectar)</label>
					<div style="display:flex; gap:0.5rem;">
						<input id="add-url" bind:value={addUrl} placeholder="https://..." style="flex:1;" />
						<button class="btn-secondary" onclick={lookupUrl} disabled={lookupLoading} style="white-space:nowrap;">
							{lookupLoading ? '…' : '🔍'}
						</button>
					</div>
					{#if lookupLoading}
						<p class="lookup-status" aria-live="polite">
							<span class="lookup-dot" aria-hidden="true"></span>
							Buscando informacion del enlace...
						</p>
					{/if}
				</div>

				<div class="form-group">
					<label for="add-type">Tipo</label>
					<select id="add-type" bind:value={addType}>
						<option value="youtube">▶️ YouTube</option>
						<option value="movie">🎬 Película</option>
						<option value="book">📖 Libro</option>
						<option value="game">🎮 Juego</option>
					</select>
				</div>

				<div class="form-group">
					<label for="add-title">Título</label>
					<input id="add-title" bind:value={addTitle} required />
				</div>

				<div class="form-group">
					<label for="add-author">Autor / Canal / Estudio</label>
					<input id="add-author" bind:value={addAuthor} />
				</div>

				<div class="form-group">
					<label for="add-duration">Duración (minutos)</label>
					<input id="add-duration" type="number" bind:value={addDuration} min="0" />
				</div>

				<div class="form-group">
					<label for="add-notes">Notas</label>
					<textarea id="add-notes" bind:value={addNotes}></textarea>
				</div>

				{#if addError}<p class="error">{addError}</p>{/if}

				<div style="display:flex; gap:0.5rem; margin-top:1rem;">
					<button onclick={submitAdd} style="flex:1;">Guardar</button>
					<button class="btn-secondary" onclick={() => { showAdd = false; resetForm(); }} style="flex:1;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}
{/if}
