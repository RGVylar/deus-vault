<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, ContentType, VaultStats, PaginatedContents } from '$lib/types';

	const LIMIT = 20;

	let contents: Content[] = $state([]);
	let stats: VaultStats | null = $state(null);
	let filter: ContentType | 'all' = $state('all');
	let loading = $state(true);
	let loadingMore = $state(false);
	let total = $state(0);
	let offset = $state(0);

	// Editable consumed date
	let editingDateId = $state<number | null>(null);
	let editDateValue = $state('');

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		load();
	});

	function buildUrl(type: ContentType | 'all', off: number) {
		let url = `/contents?consumed=true&limit=${LIMIT}&offset=${off}`;
		if (type !== 'all') url += `&content_type=${type}`;
		return url;
	}

	async function load() {
		loading = true;
		offset = 0;
		try {
			const [s, p] = await Promise.all([
				api.get<VaultStats>('/contents/stats'),
				api.get<PaginatedContents>(buildUrl(filter, 0))
			]);
			stats = s;
			contents = p.items;
			total = p.total;
		} finally { loading = false; }
	}

	async function loadMore() {
		loadingMore = true;
		const newOffset = offset + LIMIT;
		try {
			const p = await api.get<PaginatedContents>(buildUrl(filter, newOffset));
			contents = [...contents, ...p.items];
			total = p.total;
			offset = newOffset;
		} finally { loadingMore = false; }
	}

	let filterMounted = false;
	$effect(() => {
		const _filter = filter;
		if (!filterMounted) { filterMounted = true; return; }
		if (!auth.isLoggedIn) return;
		offset = 0;
		api.get<PaginatedContents>(buildUrl(_filter, 0)).then(p => {
			contents = p.items;
			total = p.total;
		});
	});

	async function unconsume(id: number) {
		await api.post(`/contents/${id}/unconsume`);
		load();
	}

	function startEditDate(c: Content) {
		editingDateId = c.id;
		// Format consumed_at as "YYYY-MM-DD" for date input
		if (c.consumed_at) {
			editDateValue = c.consumed_at.slice(0, 10);
		} else {
			editDateValue = new Date().toISOString().slice(0, 10);
		}
	}

	async function saveDate(c: Content) {
		if (!editDateValue) { editingDateId = null; return; }
		// Build an ISO datetime from the date string (noon UTC to avoid timezone day-shift)
		const isoDate = `${editDateValue}T12:00:00Z`;
		editingDateId = null;
		contents = contents.map(x => x.id === c.id ? { ...x, consumed_at: isoDate } : x);
		await api.patch(`/contents/${c.id}`, { consumed_at: isoDate });
	}
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}
	<h1>Consumido</h1>

	{#if stats}
		<div class="hero-number" style="padding:0.5rem 0;">
			<div class="number" style="font-size:2rem;">{formatDuration(stats.total_consumed_minutes)}</div>
			<div class="unit">de contenido consumido</div>
		</div>
		<div class="stat-row">
			<div class="stat-pill">
				<span>✅</span> <span class="val">{stats.consumed_count}</span> items
			</div>
		</div>
	{/if}

	<div class="tabs">
		<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
		<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬</button>
		<button class:btn-secondary={filter !== 'series'} onclick={() => filter = 'series'}>📺</button>
		<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖</button>
		<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮</button>
	</div>

	{#if loading}
		<p style="text-align:center; color:var(--text-muted);">Cargando…</p>
	{:else if contents.length === 0}
		<div class="card" style="text-align:center; padding:2rem;">
			<p style="color:var(--text-muted);">Aún no has consumido nada. ¡A ello!</p>
		</div>
	{:else}
		<div style="display:flex; flex-direction:column; gap:0.5rem;">
			{#each contents as c (c.id)}
				{@const link = buildConsumeUrl(c)}
				<div class="content-card" style="opacity:0.75;">
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
							{#if c.content_type === 'series'}
								{#if c.seasons && c.seasons > 0}<span>📺 {c.seasons}T</span>{/if}
								{#if c.episode_count && c.episode_count > 0}<span>{c.episode_count} ep</span>{/if}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}/ep</span>{/if}
								{#if c.episode_count && c.episode_count > 0 && c.duration_minutes > 0}
									<span class="series-total">~{formatDuration(c.duration_minutes * c.episode_count)} total</span>
								{/if}
							{:else if c.duration_minutes > 0}
								<span>⏱ {formatDuration(c.duration_minutes)}</span>
							{/if}
							<!-- Consumed date (editable) -->
							{#if editingDateId === c.id}
								<span class="date-edit-wrap">
									<input
										type="date"
										bind:value={editDateValue}
										class="date-input"
										onblur={() => saveDate(c)}
										onkeydown={(e) => { if (e.key === 'Enter') saveDate(c); if (e.key === 'Escape') editingDateId = null; }}
										autofocus
									/>
									<button class="btn-secondary date-save-btn" onclick={() => saveDate(c)}>✓</button>
								</span>
							{:else if c.consumed_at}
								<button class="date-btn" onclick={() => startEditDate(c)} title="Editar fecha">
									📅 {new Date(c.consumed_at).toLocaleDateString('es')}
								</button>
							{:else}
								<button class="date-btn date-btn-empty" onclick={() => startEditDate(c)} title="Añadir fecha">
									📅 Sin fecha
								</button>
							{/if}
						</div>
						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn-secondary">Abrir</button>
								</a>
							{/if}
							<button class="btn-secondary" onclick={() => unconsume(c.id)}>↩ Devolver</button>
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if contents.length < total}
			<div style="text-align:center; margin: 1rem 0 2rem;">
				<button class="btn-secondary" onclick={loadMore} disabled={loadingMore}>
					{loadingMore ? 'Cargando…' : `Cargar más (${total - contents.length} restantes)`}
				</button>
			</div>
		{/if}
	{/if}
{/if}

<style>
	/* Editable consumed date */
	.date-btn {
		all: unset;
		cursor: pointer;
		font-size: 0.72rem;
		color: var(--text-muted);
		border-bottom: 1px dashed var(--border);
		padding-bottom: 1px;
		transition: color 0.15s;
	}
	.date-btn:hover { color: var(--primary); border-bottom-color: var(--primary); }
	.date-btn-empty { opacity: 0.5; }
	.date-btn-empty:hover { opacity: 1; }

	.date-edit-wrap {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.date-input {
		font-size: 0.75rem;
		padding: 0.15rem 0.35rem;
		border-radius: 6px;
	}
	.date-save-btn {
		font-size: 0.72rem;
		padding: 0.15rem 0.4rem;
	}
</style>
