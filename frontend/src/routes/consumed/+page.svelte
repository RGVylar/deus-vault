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
	let tab: 'consumed' | 'abandoned' = $state('consumed');
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
		let url = tab === 'consumed'
			? `/contents?consumed=true&limit=${LIMIT}&offset=${off}`
			: `/contents?abandoned=true&limit=${LIMIT}&offset=${off}`;
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

	let controlsMounted = false;
	$effect(() => {
		const _filter = filter;
		const _tab = tab;
		if (!controlsMounted) { controlsMounted = true; return; }
		if (!auth.isLoggedIn) return;
		offset = 0;
		loading = true;
		api.get<PaginatedContents>(buildUrl(_filter, 0)).then(p => {
			contents = p.items;
			total = p.total;
		}).finally(() => { loading = false; });
	});

	async function unconsume(id: number) {
		await api.post(`/contents/${id}/unconsume`);
		load();
	}

	async function restore(id: number) {
		await api.post(`/contents/${id}/restore`);
		load();
	}

	async function consume(id: number) {
		await api.post(`/contents/${id}/consume`);
		load();
	}

	function startEditDate(c: Content) {
		editingDateId = c.id;
		if (c.consumed_at) {
			editDateValue = c.consumed_at.slice(0, 10);
		} else {
			editDateValue = new Date().toISOString().slice(0, 10);
		}
	}

	async function saveDate(c: Content) {
		if (!editDateValue) { editingDateId = null; return; }
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

	<!-- Desktop topbar -->
	<div class="desk-topbar desk-only">
		<h1 class="desk-title">{tab === 'consumed' ? 'Consumido' : 'Abandonado'}</h1>
	</div>

	{#if stats}
		<!-- Hero + logros grid -->
		<div class="desk-hero-grid">
			<div class="hero" style="padding:16px 12px;">
				{#if tab === 'consumed'}
					<div class="kicker">TOTAL CONSUMIDO</div>
					<div class="number" style="font-size:clamp(40px,14vw,80px); background:linear-gradient(180deg,#fff,oklch(0.84 0.17 150)); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; filter:drop-shadow(0 0 30px oklch(0.80 0.18 150 / 0.4));">{formatDuration(stats.total_consumed_minutes)}</div>
					<div class="unit">{stats.consumed_count} ítems completados</div>
				{:else}
					<div class="kicker">ABANDONADO</div>
					<div class="number" style="font-size:clamp(40px,14vw,80px); background:linear-gradient(180deg,#fff,oklch(0.70 0.18 25)); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; filter:drop-shadow(0 0 30px oklch(0.65 0.20 25 / 0.4));">{stats.abandoned_count}</div>
					<div class="unit">{stats.abandoned_count === 1 ? 'ítem abandonado' : 'ítems abandonados'}</div>
				{/if}
			</div>

			<!-- Stats card: desktop only -->
			<div class="desk-quick desk-only">
				{#if tab === 'consumed'}
					<h3>Logros</h3>
					<div class="dq-row">
						<span class="lbl">✅ Total consumido</span>
						<span class="val">{stats.consumed_count}</span>
					</div>
					<div class="dq-row">
						<span class="lbl">⏱ Tiempo total</span>
						<span class="val" style="font-size:13px;">{formatDuration(stats.total_consumed_minutes)}</span>
					</div>
					{#if stats.consumed_count > 0}
						<div class="dq-row">
							<span class="lbl">📊 Media por ítem</span>
							<span class="val" style="font-size:13px;">{formatDuration(Math.round(stats.total_consumed_minutes / stats.consumed_count))}</span>
						</div>
					{/if}
					<div class="dq-row">
						<span class="lbl">📦 Aún pendientes</span>
						<span class="val">{stats.pending_count}</span>
					</div>
					<div class="dq-row" style="border-bottom:none;">
						<span class="lbl">🚫 Abandonados</span>
						<span class="val">{stats.abandoned_count}</span>
					</div>
				{:else}
					<h3>Abandonado</h3>
					<div class="dq-row">
						<span class="lbl">🚫 Total abandonado</span>
						<span class="val">{stats.abandoned_count}</span>
					</div>
					<div class="dq-row">
						<span class="lbl">✅ Completados</span>
						<span class="val">{stats.consumed_count}</span>
					</div>
					<div class="dq-row" style="border-bottom:none;">
						<span class="lbl">📦 Pendientes</span>
						<span class="val">{stats.pending_count}</span>
					</div>
				{/if}
			</div>
		</div>

		<!-- Mobile-only pill -->
		<div class="pill-row mobile-only">
			{#if tab === 'consumed'}
				<div class="pill">
					<span>✅</span> <span class="val">{stats.consumed_count}</span> <span class="lbl">completados</span>
				</div>
			{:else}
				<div class="pill">
					<span>🚫</span> <span class="val">{stats.abandoned_count}</span> <span class="lbl">abandonados</span>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Tab switcher: Consumido / Abandonado -->
	<div class="seg" style="margin-bottom: 12px;">
		<button class:active={tab === 'consumed'} onclick={() => tab = 'consumed'}>✅ Completado</button>
		<button class:active={tab === 'abandoned'} onclick={() => tab = 'abandoned'}>🚫 Abandonado</button>
	</div>

	<!-- Type filter -->
	<div class="tabs desk-tabs">
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
			<span class="icon">{tab === 'consumed' ? '✅' : '🚫'}</span>
			<p>{tab === 'consumed' ? '¡Aún no has consumido nada. A ello!' : 'Ningún ítem abandonado.'}</p>
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
						<div class="title">
						{c.title}
						{#if c.times_consumed && c.times_consumed > 1}
							<span class="times-badge" title="{c.times_consumed} veces consumido">×{c.times_consumed}</span>
						{/if}
					</div>
						<div class="meta">
							<span class="badge">{TYPE_LABELS[c.content_type]}</span>
							{#if c.rating}
								<span class="rating-badge">★ {c.rating.toFixed(1)}</span>
							{/if}
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
							<!-- Date -->
							{#if tab === 'consumed'}
								{#if editingDateId === c.id}
									<span class="date-edit-wrap">
										<!-- svelte-ignore a11y_autofocus -->
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
							{:else if c.abandoned_at}
								<span class="date-btn" style="cursor:default;">🚫 {new Date(c.abandoned_at).toLocaleDateString('es')}</span>
							{/if}
						</div>
						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn">Abrir</button>
								</a>
							{/if}
							{#if tab === 'consumed'}
								<button class="btn" onclick={() => unconsume(c.id)}>↩ Devolver</button>
							{:else}
								<button class="btn btn-consume" onclick={() => consume(c.id)} title="Marcar como completado">✓ Completar</button>
								<button class="btn" onclick={() => restore(c.id)} title="Retomar">↩ Retomar</button>
							{/if}
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

	.times-badge {
		display: inline-block;
		font-size: 10px;
		font-weight: 800;
		background: var(--primary);
		color: #fff;
		border-radius: 6px;
		padding: 1px 6px;
		margin-left: 5px;
		vertical-align: middle;
		opacity: 0.9;
	}
	.rating-badge {
		font-size: 10px;
		font-weight: 700;
		color: oklch(0.85 0.18 85);
		background: oklch(0.28 0.08 85 / 0.5);
		border: 1px solid oklch(0.65 0.15 85 / 0.4);
		border-radius: 5px;
		padding: 1px 5px;
	}
</style>
