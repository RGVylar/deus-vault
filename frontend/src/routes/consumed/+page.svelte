<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, ContentType, VaultStats, TypeStats, AbandonedTopItem, PaginatedContents } from '$lib/types';

	const LIMIT = 20;

	let contents: Content[] = $state([]);
	let stats: VaultStats | null = $state(null);
	let filter: ContentType | 'all' = $state('all');
	let tab: 'consumed' | 'abandoned' = $state('consumed');
	let loading = $state(true);
	let loadingMore = $state(false);
	let total = $state(0);
	let offset = $state(0);
	let loadError = $state<string | null>(null);

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
		loadError = null;
		offset = 0;
		try {
			const [s, p] = await Promise.all([
				api.get<VaultStats>('/contents/stats'),
				api.get<PaginatedContents>(buildUrl(filter, 0))
			]);
			stats = s;
			contents = p.items;
			total = p.total;
		} catch (e: any) {
			loadError = e?.message ?? 'Error desconocido';
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

	{#if loadError}
		<div class="load-error">
			⚠️ Error al cargar: <code>{loadError}</code>
			<button onclick={load}>Reintentar</button>
		</div>
	{/if}

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

					{#if stats.consumed_by_type && Object.keys(stats.consumed_by_type).length > 0}
						{@const byTypeSorted = Object.entries(stats.consumed_by_type)
							.sort((a, b) => b[1].minutes - a[1].minutes)}
						<div class="type-breakdown">
							<div class="tb-header">Por tipo</div>
							{#each byTypeSorted as [type, ts]}
								{@const avgMin = ts.count > 0 ? Math.round(ts.minutes / ts.count) : 0}
								<div class="tb-row" style="--tc:{TYPE_COLOR[type] ?? 'var(--primary)'}">
									<span class="tb-icon">{TYPE_ICONS[type] ?? '📄'}</span>
									<span class="tb-label">{TYPE_LABELS[type] ?? type}</span>
									<span class="tb-count">{ts.count}</span>
									<span class="tb-time">{formatDuration(ts.minutes)}</span>
									{#if avgMin > 0}
										<span class="tb-avg">~{formatDuration(avgMin)}/ítem</span>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
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

		<!-- ── Abandoned stats panel ── -->
		{#if tab === 'abandoned'}
			{@const ratio = stats.consumed_count + stats.abandoned_count > 0
				? Math.round(stats.consumed_count / (stats.consumed_count + stats.abandoned_count) * 100)
				: null}
			{@const typeRateSorted = Object.entries(stats.abandoned_by_type_rate ?? {})
				.sort((a, b) => b[1] - a[1])}

			<!-- 4 stat cards -->
			<div class="ab-stat-row">
				<div class="ab-stat glass-card">
					<div class="ab-stat-ico">⏱</div>
					<div class="ab-stat-val" style="color:var(--red)">{formatDuration(stats.abandoned_minutes)}</div>
					<div class="ab-stat-lbl">Tiempo invertido en abandonos</div>
					<div class="ab-stat-sub">que nunca volverás a ver</div>
				</div>
				<div class="ab-stat glass-card">
					<div class="ab-stat-ico">📍</div>
					<div class="ab-stat-val" style="color:var(--red)">{stats.abandoned_avg_pct != null ? `${stats.abandoned_avg_pct}%` : '—'}</div>
					<div class="ab-stat-lbl">Punto medio de abandono</div>
					<div class="ab-stat-sub">{stats.abandoned_avg_pct != null && stats.abandoned_avg_pct < 30 ? 'Sueles rendirte muy pronto' : stats.abandoned_avg_pct != null && stats.abandoned_avg_pct < 60 ? 'Te quedas a mitad de camino' : 'Abandonas casi al final 😬'}</div>
				</div>
				<div class="ab-stat glass-card">
					<div class="ab-stat-ico">😬</div>
					{#if stats.abandoned_top_items.length > 0}
						<div class="ab-stat-val" style="color:oklch(0.70 0.18 25)">{stats.abandoned_top_items[0].progress}%</div>
						<div class="ab-stat-lbl">El que más cerca estuvo</div>
						<div class="ab-stat-sub">{stats.abandoned_top_items[0].title}</div>
					{:else}
						<div class="ab-stat-val" style="color:var(--text-dim)">—</div>
						<div class="ab-stat-lbl">El que más cerca estuvo</div>
					{/if}
				</div>
				<div class="ab-stat glass-card">
					<div class="ab-stat-ico">⚖️</div>
					<div class="ab-stat-val" style="color:{ratio != null && ratio >= 70 ? 'var(--green)' : 'oklch(0.70 0.18 25)'}">{ratio != null ? `${ratio}%` : '—'}</div>
					<div class="ab-stat-lbl">Tasa de finalización</div>
					<div class="ab-stat-sub">{stats.consumed_count} completados · {stats.abandoned_count} abandonados</div>
				</div>
			</div>

			<!-- Cemetery + type rates -->
			<div class="ab-two-col">

				<!-- Cementerio top 5 -->
				{#if (stats.abandoned_top_items ?? []).length > 0}
				<div class="glass-card ab-cemetery">
					<div class="ab-section-title">⚰️ El cementerio — más cerca de terminar</div>
					{#each (stats.abandoned_top_items ?? []) as item}
						<div class="ab-grave">
							<div class="ab-grave-thumb">
								{#if item.thumbnail}
									<img src={item.thumbnail} alt="" />
								{:else}
									<span>{TYPE_ICONS[item.content_type as ContentType] ?? '📄'}</span>
								{/if}
							</div>
							<div class="ab-grave-info">
								<div class="ab-grave-title">{item.title}</div>
								<div class="ab-grave-meta">{TYPE_LABELS[item.content_type as ContentType] ?? item.content_type}{item.duration_minutes > 0 ? ` · ${formatDuration(item.duration_minutes)}` : ''}</div>
								<div class="ab-grave-bar-row">
									<div class="ab-grave-track">
										<div class="ab-grave-fill" style="width:{item.progress}%"></div>
									</div>
									<span class="ab-grave-pct">{item.progress}%</span>
								</div>
							</div>
						</div>
					{/each}
				</div>
				{/if}

				<div style="display:flex; flex-direction:column; gap:14px;">

					<!-- Tasa de abandono por tipo -->
					{#if typeRateSorted.length > 0}
					<div class="glass-card ab-type-rates">
						<div class="ab-section-title">🎯 Tasa de abandono por tipo</div>
						{#each typeRateSorted as [type, rate]}
							<div class="ab-bar-row">
								<span class="ab-bar-label" style="color:{TYPE_COLOR[type] ?? 'var(--text-muted)'}">
									{TYPE_ICONS[type as ContentType] ?? '📄'} {TYPE_LABELS[type as ContentType] ?? type}
								</span>
								<div class="ab-bar-track">
									<div class="ab-bar-fill" style="width:{rate}%; background:{TYPE_COLOR[type] ?? 'var(--primary)'}"></div>
								</div>
								<span class="ab-bar-val">{rate}%</span>
							</div>
						{/each}
					</div>
					{/if}

					<!-- En el limbo -->
					{#if stats.abandoned_stale_count > 0}
					<div class="glass-card ab-limbo">
						<div class="ab-section-title">⏳ En el limbo
							<span class="ab-limbo-badge">{stats.abandoned_stale_count}</span>
						</div>
						<div class="ab-limbo-sub">Abandonados hace más de 6 meses sin que los toques</div>
						{#each contents.filter(c => {
							if (!c.abandoned_at) return false;
							const d = new Date(c.abandoned_at);
							return (Date.now() - d.getTime()) > 180 * 24 * 60 * 60 * 1000;
						}).slice(0, 3) as c}
							<div class="ab-limbo-row">
								<span class="ab-limbo-title">{TYPE_ICONS[c.content_type] ?? '📄'} {c.title}</span>
								<span class="ab-limbo-age" style="color:{
									(Date.now() - new Date(c.abandoned_at!).getTime()) > 365 * 24 * 60 * 60 * 1000
										? 'var(--red)' : 'oklch(0.70 0.18 55)'}">
									{Math.round((Date.now() - new Date(c.abandoned_at!).getTime()) / (30 * 24 * 60 * 60 * 1000))} meses
								</span>
							</div>
						{/each}
					</div>
					{/if}

				</div>
			</div>
		{/if}

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
						{#if tab === 'abandoned' && c.progress != null && c.progress > 0}
							<div class="progress-wrap">
								<div class="progress-track">
									<div class="progress-fill" style="width:{c.progress}%"></div>
								</div>
								<span class="progress-pct">{c.progress}%</span>
							</div>
						{/if}
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

	/* ── Load error ── */
	.load-error {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		padding: 10px 14px;
		margin-bottom: 12px;
		background: oklch(0.65 0.20 25 / 0.12);
		border: 1px solid oklch(0.65 0.20 25 / 0.35);
		border-radius: var(--radius-xs);
		font-size: 13px;
		color: oklch(0.80 0.15 25);
	}
	.load-error code {
		font-family: monospace;
		font-size: 12px;
		background: rgba(0,0,0,0.3);
		padding: 2px 6px;
		border-radius: 5px;
		flex: 1;
	}
	.load-error button {
		all: unset;
		cursor: pointer;
		font-size: 12px;
		font-weight: 700;
		padding: 4px 10px;
		border-radius: 8px;
		background: oklch(0.65 0.20 25 / 0.25);
		border: 1px solid oklch(0.65 0.20 25 / 0.4);
		color: oklch(0.85 0.15 25);
		transition: background 0.15s;
	}
	.load-error button:hover { background: oklch(0.65 0.20 25 / 0.4); }

	/* ── Abandoned stats panel ── */
	:global(:root) {
		--red: oklch(0.65 0.20 25);
		--green: oklch(0.72 0.20 150);
	}
	.glass-card {
		background: var(--glass-bg);
		backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-sm);
		box-shadow: var(--glass-shadow), var(--glass-inner);
		position: relative;
		overflow: hidden;
	}
	.glass-card::after {
		content: '';
		position: absolute;
		top: 0; left: 8%; right: 8%; height: 1px;
		background: linear-gradient(90deg, transparent, var(--glass-shine), transparent);
		pointer-events: none;
	}

	/* 4 stat cards */
	.ab-stat-row {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 10px;
		margin-bottom: 12px;
	}
	@media (min-width: 700px) {
		.ab-stat-row { grid-template-columns: repeat(4, 1fr); }
	}
	.ab-stat {
		padding: 16px 16px 14px;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.ab-stat::before {
		content: '';
		position: absolute;
		top: 0; left: 0; right: 0; height: 2px;
		background: linear-gradient(90deg, transparent, oklch(0.65 0.20 25 / 0.8), transparent);
	}
	.ab-stat-ico  { font-size: 20px; margin-bottom: 2px; }
	.ab-stat-val  { font-size: 26px; font-weight: 900; letter-spacing: -0.03em; line-height: 1; }
	.ab-stat-lbl  { font-size: 11px; color: var(--text-muted); font-weight: 600; margin-top: 2px; }
	.ab-stat-sub  { font-size: 10px; color: var(--text-dim); font-style: italic; }

	/* Two-column layout */
	.ab-two-col {
		display: grid;
		grid-template-columns: 1fr;
		gap: 12px;
		margin-bottom: 16px;
	}
	@media (min-width: 800px) {
		.ab-two-col { grid-template-columns: 1fr 1fr; }
	}

	/* Cemetery */
	.ab-cemetery { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
	.ab-section-title {
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--text-dim);
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 2px;
	}
	.ab-grave {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		background: rgba(255,255,255,0.025);
		border: 1px solid var(--glass-border);
		border-radius: 10px;
	}
	.ab-grave-thumb {
		width: 44px; height: 44px; border-radius: 8px;
		flex-shrink: 0; overflow: hidden;
		background: rgba(255,255,255,0.06);
		display: flex; align-items: center; justify-content: center; font-size: 18px;
	}
	.ab-grave-thumb img { width: 100%; height: 100%; object-fit: cover; }
	.ab-grave-info { flex: 1; min-width: 0; }
	.ab-grave-title {
		font-size: 12px; font-weight: 600;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.ab-grave-meta { font-size: 10px; color: var(--text-dim); margin-top: 1px; }
	.ab-grave-bar-row { display: flex; align-items: center; gap: 7px; margin-top: 5px; }
	.ab-grave-track {
		flex: 1; height: 4px; background: rgba(255,255,255,0.07);
		border-radius: 99px; overflow: hidden;
	}
	.ab-grave-fill {
		height: 100%; border-radius: 99px;
		background: oklch(0.65 0.20 25);
		box-shadow: 0 0 6px oklch(0.65 0.20 25 / 0.5);
	}
	.ab-grave-pct { font-size: 11px; font-weight: 800; color: oklch(0.70 0.18 25); flex-shrink: 0; }

	/* Type rates */
	.ab-type-rates { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
	.ab-bar-row { display: flex; align-items: center; gap: 8px; }
	.ab-bar-label {
		font-size: 11px; font-weight: 600;
		width: 90px; flex-shrink: 0;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.ab-bar-track { flex: 1; height: 5px; background: rgba(255,255,255,0.07); border-radius: 99px; overflow: hidden; }
	.ab-bar-fill   { height: 100%; border-radius: 99px; }
	.ab-bar-val    { font-size: 11px; font-weight: 700; color: var(--text-muted); width: 34px; text-align: right; flex-shrink: 0; }

	/* Limbo */
	.ab-limbo { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
	.ab-limbo-badge {
		background: oklch(0.65 0.20 25 / 0.2);
		color: oklch(0.70 0.18 25);
		border: 1px solid oklch(0.65 0.20 25 / 0.35);
		border-radius: 99px;
		font-size: 10px;
		font-weight: 800;
		padding: 1px 7px;
	}
	.ab-limbo-sub { font-size: 11px; color: var(--text-dim); font-style: italic; margin-top: -2px; }
	.ab-limbo-row {
		display: flex; align-items: center; justify-content: space-between;
		padding: 7px 10px;
		background: rgba(255,255,255,0.025);
		border: 1px solid var(--glass-border);
		border-radius: 9px;
		gap: 8px;
	}
	.ab-limbo-title { font-size: 12px; font-weight: 500; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.ab-limbo-age   { font-size: 11px; font-weight: 800; flex-shrink: 0; }

	/* ── Abandoned progress bar ── */
	.progress-wrap {
		display: flex;
		align-items: center;
		gap: 7px;
		margin-top: 2px;
	}
	.progress-wrap .progress-track {
		flex: 1;
		height: 4px;
		background: rgba(255,255,255,0.08);
		border-radius: 4px;
		overflow: hidden;
		margin-top: 0;
	}
	.progress-wrap .progress-fill {
		height: 100%;
		background: oklch(0.65 0.18 25);
		border-radius: 4px;
		box-shadow: 0 0 6px oklch(0.60 0.20 25 / 0.6);
	}
	.progress-pct {
		font-size: 11px;
		font-weight: 700;
		color: oklch(0.70 0.18 25);
		white-space: nowrap;
		flex-shrink: 0;
	}

	/* ── Type breakdown in desk-quick ── */
	.type-breakdown {
		margin-top: 14px;
		padding-top: 10px;
		border-top: 1px solid var(--glass-border);
	}
	.tb-header {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-dim);
		margin-bottom: 8px;
	}
	.tb-row {
		display: grid;
		grid-template-columns: 18px 1fr auto auto;
		grid-template-rows: auto auto;
		column-gap: 6px;
		row-gap: 0;
		align-items: center;
		padding: 5px 0;
		border-bottom: 1px solid var(--glass-border);
	}
	.tb-row:last-child { border-bottom: none; }

	.tb-icon {
		grid-column: 1;
		grid-row: 1 / 3;
		font-size: 13px;
		line-height: 1;
	}
	.tb-label {
		grid-column: 2;
		grid-row: 1;
		font-size: 12px;
		font-weight: 600;
		color: var(--tc);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.tb-count {
		grid-column: 3;
		grid-row: 1;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		text-align: right;
		white-space: nowrap;
	}
	.tb-time {
		grid-column: 4;
		grid-row: 1;
		font-size: 11px;
		font-weight: 700;
		color: var(--text);
		text-align: right;
		white-space: nowrap;
	}
	.tb-avg {
		grid-column: 2 / 5;
		grid-row: 2;
		font-size: 10px;
		color: var(--text-dim);
		font-style: italic;
		padding-top: 1px;
	}
</style>
