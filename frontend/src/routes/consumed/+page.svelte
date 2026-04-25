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

	const TYPE_COLOR: Record<string, string> = {
		youtube: 'var(--youtube)',
		movie:   'var(--movie)',
		series:  'var(--series)',
		book:    'var(--book)',
		game:    'var(--game)',
		music:   'var(--music)',
	};
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">Redirigiendo…</p>
{:else}
	<h1>Consumido</h1>

	{#if stats}
		<div class="hero" style="padding:16px 12px;">
			<div class="kicker">TOTAL CONSUMIDO</div>
			<div class="number" style="font-size:clamp(40px,14vw,80px);">{formatDuration(stats.total_consumed_minutes)}</div>
			<div class="unit">de contenido consumido</div>
		</div>
		<div class="pill-row">
			<div class="pill">
				<span>✅</span> <span class="val">{stats.consumed_count}</span> <span class="lbl">items</span>
			</div>
		</div>
	{/if}

	<div class="tabs">
		<button class="tab" class:active={filter === 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class="tab" class:active={filter === 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
		<button class="tab" class:active={filter === 'movie'} onclick={() => filter = 'movie'}>🎬</button>
		<button class="tab" class:active={filter === 'series'} onclick={() => filter = 'series'}>📺</button>
		<button class="tab" class:active={filter === 'book'} onclick={() => filter = 'book'}>📖</button>
		<button class="tab" class:active={filter === 'game'} onclick={() => filter = 'game'}>🎮</button>
		<button class="tab" class:active={filter === 'music'} onclick={() => filter = 'music'}>🎵</button>
	</div>

	{#if loading}
		<p class="muted center">Cargando…</p>
	{:else if contents.length === 0}
		<div class="empty">
			<span class="icon">✅</span>
			<p>Aún no has consumido nada. ¡A ello!</p>
		</div>
	{:else}
		<div class="content-grid">
			{#each contents as c (c.id)}
				{@const link = buildConsumeUrl(c)}
				{@const landscape = c.content_type === 'youtube' || c.content_type === 'movie' || c.content_type === 'series' || c.content_type === 'game'}
				<div
					class="c-card"
					class:landscape
					class:portrait={!landscape}
					style="opacity:0.85; --card-accent:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}; --accent:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}"
				>
					{#if landscape}
						<div class="thumb-land">
							{#if c.thumbnail}
								<img src={c.thumbnail} alt="" />
							{:else}
								<div class="ph">{TYPE_ICONS[c.content_type] || '📄'}</div>
							{/if}
						</div>
					{:else}
						<div class="thumb-port">
							{#if c.thumbnail}
								<img src={c.thumbnail} alt="" />
							{:else}
								<div class="ph">{TYPE_ICONS[c.content_type] || '📄'}</div>
							{/if}
						</div>
					{/if}
					<div class="info">
						<div class="title">{c.title}</div>
						<div class="meta">
							<span class="badge">{TYPE_LABELS[c.content_type]}</span>
							{#if c.content_type === 'series'}
								{#if c.seasons && c.seasons > 0}<span>📺 {c.seasons}T</span>{/if}
								{#if c.episode_count && c.episode_count > 0}<span>{c.episode_count} ep</span>{/if}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}/ep</span>{/if}
								{#if c.episode_count && c.episode_count > 0 && c.duration_minutes > 0}
									<span style="font-size:10px; font-weight:600; color:var(--series);">~{formatDuration(c.duration_minutes * c.episode_count)} total</span>
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
										class="text date-input"
										onblur={() => saveDate(c)}
										onkeydown={(e) => { if (e.key === 'Enter') saveDate(c); if (e.key === 'Escape') editingDateId = null; }}
										autofocus
									/>
									<button class="btn" onclick={() => saveDate(c)}>✓</button>
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
									<button class="btn">Abrir</button>
								</a>
							{/if}
							<button class="btn" onclick={() => unconsume(c.id)}>↩ Devolver</button>
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if contents.length < total}
			<div class="center mt16">
				<button class="btn btn-lg" onclick={loadMore} disabled={loadingMore}>
					{loadingMore ? 'Cargando…' : `Cargar más (${total - contents.length} restantes)`}
				</button>
			</div>
		{/if}
	{/if}
{/if}

<style>
	.date-btn {
		all: unset;
		cursor: pointer;
		font-size: 11px;
		color: var(--text-muted);
		border-bottom: 1px dashed var(--glass-border);
		padding-bottom: 1px;
		transition: color 0.15s;
	}
	.date-btn:hover { color: var(--primary); }
	.date-btn-empty { opacity: 0.5; }
	.date-btn-empty:hover { opacity: 1; }

	.date-edit-wrap {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}
	.date-input {
		font-size: 12px !important;
		padding: 4px 8px !important;
	}
</style>
