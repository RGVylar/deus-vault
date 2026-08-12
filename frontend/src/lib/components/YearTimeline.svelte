<script lang="ts">
	/**
	 * Línea de tiempo unificada del año: qué tenías entre manos y cuándo.
	 *
	 * No todo el contenido se consume igual, así que no todo se dibuja igual:
	 *  - Campañas (juego, serie, libro): las vives durante semanas → barra de
	 *    started_at a consumed_at. Sin started_at solo sabemos cuándo acabaste,
	 *    así que se pinta un punto en vez de inventar un tramo.
	 *  - Eventos (película): una sentada → un carril de puntos, no una fila cada una.
	 *  - Ruido (YouTube, música): son cientos de ítems → banda de intensidad mensual.
	 */
	import { onMount } from 'svelte';
	import type { Content } from '$lib/types';
	import { t, tc, fmtDate as fmtDateI18n } from '$lib/i18n/index.svelte';
	import { formatDuration, typeLabel } from '$lib/utils';
	import Icon from './Icon.svelte';

	interface Props {
		items: Content[];
		abandonedItems?: Content[];
		inProgressItems?: Content[];
		year: number;
		months: string[];
	}
	let { items, abandonedItems = [], inProgressItems = [], year, months }: Props = $props();

	const CAMPAIGN: string[] = ['game', 'series', 'manga', 'book'];
	const NOISE: string[] = ['youtube', 'music'];
	const COLORS: Record<string, string> = {
		youtube: 'var(--youtube)', movie: 'var(--movie)', series: 'var(--series)',
		book: 'var(--book)', manga: 'var(--manga)', game: 'var(--game)', music: 'var(--music)',
	};
	const LS_KEY = 'rw-timeline-view';
	const LS_EXTRA_KEY = 'rw-timeline-extra';
	type ViewMode = 'grouped' | 'mixed' | 'explore';

	let viewMode = $state<ViewMode>('grouped');
	let showExtra = $state(true);
	onMount(() => {
		try {
			const v = localStorage.getItem(LS_KEY);
			if (v === 'mixed' || v === 'explore') viewMode = v;
		} catch { /* ignore */ }
		try { showExtra = localStorage.getItem(LS_EXTRA_KEY) !== 'off'; } catch { /* ignore */ }
	});
	function setViewMode(mode: ViewMode) {
		viewMode = mode;
		try { localStorage.setItem(LS_KEY, mode); } catch { /* ignore */ }
	}
	function toggleExtra() {
		showExtra = !showExtra;
		try { localStorage.setItem(LS_EXTRA_KEY, showExtra ? 'on' : 'off'); } catch { /* ignore */ }
	}

	/** Índice de mes 0-11 dentro del año mostrado; null si la fecha cae fuera. */
	function monthIdx(iso: string | null | undefined): number | null {
		if (!iso) return null;
		const d = new Date(iso);
		if (isNaN(d.getTime()) || d.getFullYear() !== year) return null;
		return d.getMonth();
	}
	/** Posición 0-100% dentro del año, para los puntos del carril de películas. */
	function yearPct(iso: string | null | undefined): number | null {
		if (!iso) return null;
		const d = new Date(iso);
		if (isNaN(d.getTime()) || d.getFullYear() !== year) return null;
		const daysInMonth = new Date(year, d.getMonth() + 1, 0).getDate();
		return ((d.getMonth() + (d.getDate() - 1) / daysInMonth) / 12) * 100;
	}

	type BarKind = 'done' | 'abandoned' | 'progress';
	type Bar = {
		id: number; title: string; type: string; color: string; kind: BarKind;
		startPct: number; endPct: number; hasSpan: boolean; minutes: number; when: string;
	};

	function campaignMinutes(c: Content): number {
		return (c.content_type === 'series' || c.content_type === 'manga') && c.episode_count
			? c.duration_minutes * c.episode_count
			: c.duration_minutes;
	}

	const bars = $derived.by<Bar[]>(() => {
		const out: Bar[] = [];
		for (const c of items) {
			if (!CAMPAIGN.includes(c.content_type)) continue;
			const end = yearPct(c.consumed_at);
			if (end === null) continue;
			const rawStart = yearPct(c.started_at);
			const hasSpan = rawStart !== null && rawStart < end;
			out.push({
				id: c.id, title: c.title, type: c.content_type, color: COLORS[c.content_type], kind: 'done',
				startPct: hasSpan ? (rawStart as number) : end, endPct: end, hasSpan, minutes: campaignMinutes(c),
				when: c.consumed_at ? fmtDateI18n(new Date(c.consumed_at), { day: 'numeric', month: 'short' }) : '',
			});
		}
		return out;
	});

	/** Cortados a media partida — el mismo tramo, pero con el final marcado como rotura, no como meta. */
	const abandonedBars = $derived.by<Bar[]>(() => {
		const out: Bar[] = [];
		for (const c of abandonedItems) {
			if (!CAMPAIGN.includes(c.content_type)) continue;
			const end = yearPct(c.abandoned_at);
			if (end === null) continue;
			const rawStart = yearPct(c.started_at);
			const hasSpan = rawStart !== null && rawStart < end;
			out.push({
				id: c.id, title: c.title, type: c.content_type, color: COLORS[c.content_type], kind: 'abandoned',
				startPct: hasSpan ? (rawStart as number) : end, endPct: end, hasSpan, minutes: campaignMinutes(c),
				when: c.abandoned_at ? fmtDateI18n(new Date(c.abandoned_at), { day: 'numeric', month: 'short' }) : '',
			});
		}
		return out;
	});

	/** Aún abiertos — el tramo llega hasta hoy (o hasta fin de año, si el año ya pasó). */
	const inProgressBars = $derived.by<Bar[]>(() => {
		const out: Bar[] = [];
		const isCurrentYear = year === new Date().getFullYear();
		const nowPct = isCurrentYear ? yearPct(new Date().toISOString()) : null;
		for (const c of inProgressItems) {
			if (!CAMPAIGN.includes(c.content_type)) continue;
			const start = yearPct(c.started_at);
			if (start === null) continue;
			const end = nowPct !== null ? Math.max(nowPct, start + 0.4) : 100;
			out.push({
				id: c.id, title: c.title, type: c.content_type, color: COLORS[c.content_type], kind: 'progress',
				startPct: start, endPct: end, hasSpan: true, minutes: campaignMinutes(c),
				when: c.started_at ? fmtDateI18n(new Date(c.started_at), { day: 'numeric', month: 'short' }) : '',
			});
		}
		return out;
	});

	/** Lo que se dibuja: siempre lo acabado, más abandonados/en curso si el interruptor está encendido. */
	const allBars = $derived(showExtra ? [...bars, ...abandonedBars, ...inProgressBars] : bars);

	/** Agrupadas por tipo (juego, serie, libro), cada grupo ordenado por inicio. */
	const grouped = $derived.by(() => {
		return CAMPAIGN
			.map(type => ({
				type,
				rows: allBars.filter(b => b.type === type).sort((a, b) => a.startPct - b.startPct || b.endPct - a.endPct),
			}))
			.filter(g => g.rows.length > 0);
	});

	/** Todas revueltas, en orden cronológico de inicio. */
	const chrono = $derived([...allBars].sort((a, b) => a.startPct - b.startPct || (b.endPct - b.startPct) - (a.endPct - a.startPct)));

	// ── Explorar: minimapa del año entero + ventana que arrastras para enfocar un tramo ──
	// Arranca cubriendo el año completo — nada se oculta hasta que el usuario decide acotar.
	let winStart = $state(0);
	let winEnd = $state(100);
	let minimapEl: HTMLDivElement | undefined = $state();
	let dragMode: 'move' | 'left' | 'right' | null = null;
	let dragStartX = 0;
	let dragStartWin = { start: 0, end: 100 };

	function monthAt(pct: number): string {
		const idx = Math.min(months.length - 1, Math.max(0, Math.floor(pct / 100 * months.length)));
		return months[idx];
	}

	function overlapsWindow(b: Bar): boolean {
		const s = b.hasSpan ? b.startPct : b.endPct;
		return b.endPct >= winStart && s <= winEnd;
	}
	const exploreBars = $derived(allBars.filter(overlapsWindow));
	const exploreGrouped = $derived.by(() => {
		return CAMPAIGN
			.map(type => ({
				type,
				rows: exploreBars.filter(b => b.type === type).sort((a, b) => a.startPct - b.startPct || b.endPct - a.endPct),
			}))
			.filter(g => g.rows.length > 0);
	});

	function beginDrag(mode: 'move' | 'left' | 'right', ev: PointerEvent) {
		ev.preventDefault();
		ev.stopPropagation();
		dragMode = mode;
		dragStartX = ev.clientX;
		dragStartWin = { start: winStart, end: winEnd };
		window.addEventListener('pointermove', onDrag);
		window.addEventListener('pointerup', endDrag);
	}
	function onDrag(ev: PointerEvent) {
		if (!dragMode || !minimapEl) return;
		const rect = minimapEl.getBoundingClientRect();
		const deltaPct = (ev.clientX - dragStartX) / rect.width * 100;
		if (dragMode === 'move') {
			const width = dragStartWin.end - dragStartWin.start;
			const start = Math.max(0, Math.min(100 - width, dragStartWin.start + deltaPct));
			winStart = start;
			winEnd = start + width;
		} else if (dragMode === 'left') {
			winStart = Math.min(dragStartWin.end - 4, Math.max(0, dragStartWin.start + deltaPct));
		} else if (dragMode === 'right') {
			winEnd = Math.max(dragStartWin.start + 4, Math.min(100, dragStartWin.end + deltaPct));
		}
	}
	function endDrag() {
		dragMode = null;
		window.removeEventListener('pointermove', onDrag);
		window.removeEventListener('pointerup', endDrag);
	}
	/** Clic fuera de la ventana: la recentra ahí sin cambiar su anchura. */
	function minimapClick(ev: PointerEvent) {
		const target = ev.target as HTMLElement;
		if (target.closest('.mm-window')) return;
		if (!minimapEl) return;
		const rect = minimapEl.getBoundingClientRect();
		const pct = Math.min(100, Math.max(0, (ev.clientX - rect.left) / rect.width * 100));
		const width = winEnd - winStart;
		const start = Math.max(0, Math.min(100 - width, pct - width / 2));
		winStart = start;
		winEnd = start + width;
	}

	const movies = $derived(
		items
			.filter(c => c.content_type === 'movie' && yearPct(c.consumed_at) !== null)
			.map(c => ({ id: c.id, title: c.title, pct: yearPct(c.consumed_at) as number, minutes: c.duration_minutes }))
	);

	/** Minutos de ruido (YouTube + música) por mes, normalizados al pico. */
	const noise = $derived.by(() => {
		const per = new Array(12).fill(0);
		let count = 0;
		for (const c of items) {
			if (!NOISE.includes(c.content_type)) continue;
			const m = monthIdx(c.consumed_at);
			if (m === null) continue;
			per[m] += c.duration_minutes;
			count++;
		}
		const max = Math.max(1, ...per);
		return { per, max, count, total: per.reduce((a, b) => a + b, 0) };
	});

	const missingStart = $derived(bars.filter(b => !b.hasSpan).length);
	const hasExtra = $derived(abandonedBars.length > 0 || inProgressBars.length > 0);
	const hasAnything = $derived(bars.length > 0 || movies.length > 0 || noise.count > 0 || hasExtra);
</script>

{#snippet barRow(b: Bar)}
	{@const tag = b.kind === 'abandoned' ? `${formatDuration(b.minutes)} · ${t('rewind.timelineAbandonedTag')}` : b.kind === 'progress' ? t('rewind.timelineProgressTag') : ''}
	<div class="tl-row" class:extra-row={b.kind !== 'done'} title="{b.title} · {formatDuration(b.minutes)} · {b.when}">
		<span class="tl-name" class:tl-name-abandoned={b.kind === 'abandoned'}>
			{#if viewMode === 'mixed'}<i class="tl-chip" style="background:{b.color}"></i>{/if}
			{#if b.kind === 'abandoned'}<Icon name="ban" size={11} />{/if}
			{b.title}
		</span>
		{#if b.hasSpan}
			<span class="tl-track">
				<i
					class="tl-bar"
					class:tl-bar-abandoned={b.kind === 'abandoned'}
					class:tl-bar-progress={b.kind === 'progress'}
					style="left:{b.startPct}%; width:{Math.max(b.endPct - b.startPct, 0.4)}%; background:{b.color}"
				></i>
				{#if b.kind === 'progress'}<i class="tl-tip" style="left:{b.endPct}%; background:{b.color}"></i>{/if}
				{#if tag}<span class="tl-tag" class:tl-tag-abandoned={b.kind === 'abandoned'} style="left:calc({b.startPct}% + {Math.max(b.endPct - b.startPct, 0.4)}% + 8px)">{tag}</span>{/if}
			</span>
		{:else}
			<span class="tl-track"><i class="tl-dot" class:tl-dot-abandoned={b.kind === 'abandoned'} style="left:{b.endPct}%; background:{b.color}"></i></span>
		{/if}
	</div>
{/snippet}

{#if hasAnything}
<section class="rewind-section">
	<h2>
		<span class="hico"><Icon name="activity" size={15} /></span>
		{t('rewind.yearTimeline')}
		<div class="tl-toggle" role="group" aria-label={t('rewind.timelineViewLabel')}>
			<button type="button" aria-pressed={viewMode === 'grouped'} onclick={() => setViewMode('grouped')}>{t('rewind.timelineGrouped')}</button>
			<button type="button" aria-pressed={viewMode === 'mixed'} onclick={() => setViewMode('mixed')}>{t('rewind.timelineMixed')}</button>
			<button type="button" aria-pressed={viewMode === 'explore'} onclick={() => setViewMode('explore')}>{t('rewind.timelineExplore')}</button>
		</div>
		{#if hasExtra}
			<button type="button" class="tl-extra-toggle" class:on={showExtra} aria-pressed={showExtra} onclick={toggleExtra}>
				<Icon name={showExtra ? 'eye' : 'eyeOff'} size={12} />
				{t('rewind.timelineShowExtra')}
			</button>
		{/if}
	</h2>

	<div class="surface tl-surface">
		<div class="tl-scroll">
			<div class="tl-body">
				{#if viewMode !== 'explore'}
					<div class="tl-lines" aria-hidden="true">
						{#each months as _m}<span></span>{/each}
					</div>

					<div class="tl-axis">
						<span class="tl-axis-label">{t('rewind.timelineAxis')}</span>
						{#each months as m}<span>{m.slice(0, 1)}</span>{/each}
					</div>
				{/if}

				{#if viewMode === 'mixed'}
					<div class="tl-group">
						{#each chrono as b (`${b.kind}-${b.id}`)}
							{@render barRow(b)}
						{/each}
					</div>
				{:else if viewMode === 'explore'}
					<div class="mm-wrap">
						<div class="mm-caption">
							<span>{t('rewind.timelineExploreHint')}</span>
							<span><b>{monthAt(winStart)} – {monthAt(winEnd)}</b> · {tc('rewind.timelineExploreCount', exploreBars.length, { total: allBars.length })}</span>
						</div>
						<div
							class="minimap"
							bind:this={minimapEl}
							onpointerdown={minimapClick}
							role="slider"
							tabindex="0"
							aria-label={t('rewind.timelineExploreHint')}
							aria-valuemin={0}
							aria-valuemax={100}
							aria-valuenow={Math.round((winStart + winEnd) / 2)}
							aria-valuetext="{monthAt(winStart)} – {monthAt(winEnd)}"
						>
							<div class="mm-months" aria-hidden="true">
								{#each months as _m}<span></span>{/each}
							</div>
							<div class="mm-bands">
								{#each grouped as g (g.type)}
									<div class="mm-band">
										{#each g.rows as b (`${b.kind}-${b.id}`)}
											{#if b.hasSpan}
												<i
													class="mm-bar"
													class:mm-bar-abandoned={b.kind === 'abandoned'}
													class:mm-bar-progress={b.kind === 'progress'}
													style="left:{b.startPct}%; width:{Math.max(b.endPct - b.startPct, 0.4)}%; background:{b.color}"
												></i>
											{:else}
												<i class="mm-dot" style="left:{b.endPct}%; background:{b.color}"></i>
											{/if}
										{/each}
									</div>
								{/each}
							</div>
							<div class="mm-window" style="left:{winStart}%; width:{winEnd - winStart}%" role="button" tabindex="0" onpointerdown={(ev) => beginDrag('move', ev)}>
								<div class="mm-handle mm-handle-left" role="button" tabindex="0" onpointerdown={(ev) => beginDrag('left', ev)}></div>
								<div class="mm-handle mm-handle-right" role="button" tabindex="0" onpointerdown={(ev) => beginDrag('right', ev)}></div>
							</div>
						</div>
						<div class="mm-axis">
							{#each months as m}<span>{m.slice(0, 1)}</span>{/each}
						</div>

						{#if exploreGrouped.length === 0}
							<div class="tl-explore-empty">{t('rewind.timelineExploreEmpty')}</div>
						{:else}
							<div class="tl-explore-scroll">
								<div class="tl-explore-axis">
									<span class="tl-axis-label">{t('rewind.timelineAxis')}</span>
									{#each months as m}<span>{m.slice(0, 1)}</span>{/each}
								</div>
								{#each exploreGrouped as g (g.type)}
									<div class="tl-group">
										<div class="tl-glabel" style="color:{COLORS[g.type]}">
											{typeLabel(g.type)} <span class="c">{g.rows.length}</span>
										</div>
										{#each g.rows as b (`${b.kind}-${b.id}`)}
											{@render barRow(b)}
										{/each}
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{:else}
					{#each grouped as g (g.type)}
						<div class="tl-group">
							<div class="tl-glabel" style="color:{COLORS[g.type]}">
								{typeLabel(g.type)} <span class="c">{g.rows.length}</span>
							</div>
							{#each g.rows as b (`${b.kind}-${b.id}`)}
								{@render barRow(b)}
							{/each}
						</div>
					{/each}
				{/if}

				{#if movies.length > 0}
					<div class="tl-group">
						<div class="tl-glabel" style="color:{COLORS.movie}">
							{typeLabel('movie')} <span class="c">{movies.length}</span>
						</div>
						<div class="tl-row">
							<span class="tl-name tl-name-dim">{t('rewind.timelineEachDot')}</span>
							<span class="tl-dots">
								{#each movies as mv (mv.id)}
									<i style="left:{mv.pct}%; background:{COLORS.movie}" title="{mv.title} · {formatDuration(mv.minutes)}"></i>
								{/each}
							</span>
						</div>
					</div>
				{/if}

				{#if noise.count > 0}
					<div class="tl-group">
						<div class="tl-glabel" style="color:{COLORS.youtube}">
							{t('rewind.timelineNoise')} <span class="c">{noise.count}</span>
						</div>
						<div class="tl-row">
							<span class="tl-name tl-name-dim">{t('rewind.timelineIntensity')}</span>
							<span class="tl-ribbon">
								{#each noise.per as mins, i}
									<span
										style="opacity:{mins === 0 ? 0 : 0.25 + (mins / noise.max) * 0.75}; background:{COLORS.youtube}"
										title="{months[i]} · {formatDuration(mins)}"
									></span>
								{/each}
							</span>
						</div>
					</div>
				{/if}
			</div>
		</div>

		<div class="tl-legend">
			<span><i class="lg-bar"></i> {t('rewind.timelineLegendSpan')}</span>
			<span><i class="lg-dot"></i> {t('rewind.timelineLegendDot')}</span>
			{#if showExtra && abandonedBars.length > 0}
				<span><i class="lg-abandon"></i> {t('rewind.timelineLegendAbandoned')}</span>
			{/if}
			{#if showExtra && inProgressBars.length > 0}
				<span><i class="lg-progress"></i> {t('rewind.timelineLegendProgress')}</span>
			{/if}
			{#if missingStart > 0}
				<span class="lg-hint">{t('rewind.timelineNoStartHint', { count: missingStart })}</span>
			{/if}
		</div>
	</div>
</section>
{/if}

<style>
	/* El estilo de .rewind-section h2 vive en la pagina y el CSS de Svelte esta
	   aislado por componente, asi que aqui no llega: hay que repetirlo o el
	   icono, el titulo y el interruptor caen cada uno en una linea. */
	.rewind-section h2 {
		font-size: 12px; font-weight: 800; text-transform: uppercase;
		letter-spacing: 0.18em; color: var(--text-muted); margin-bottom: 11px;
		display: flex; align-items: center; gap: 10px;
	}
	.rewind-section h2 .hico { color: var(--primary); display: grid; place-items: center; flex-shrink: 0; opacity: 0.8; }
	.tl-toggle { display: flex; gap: 2px; margin-left: auto; background: var(--glass-bg-strong); border: 1px solid var(--glass-border); padding: 2px; border-radius: 8px; }
	.tl-toggle button {
		font-size: 10px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase;
		padding: 5px 10px; border: 0; border-radius: 6px; cursor: pointer;
		background: transparent; color: var(--text-dim); font-family: inherit;
	}
	.tl-toggle button[aria-pressed="true"] { background: var(--glass-bg); color: var(--text); }
	.tl-toggle button:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }

	.tl-extra-toggle {
		display: flex; align-items: center; gap: 5px;
		font-size: 10px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;
		padding: 5px 10px; border: 1px solid var(--glass-border); border-radius: 8px;
		background: var(--glass-bg-strong); color: var(--text-dim); cursor: pointer; font-family: inherit;
	}
	.tl-extra-toggle.on { color: var(--text); border-color: var(--danger, #e0556b); }
	.tl-extra-toggle:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }

	.tl-surface { padding: 16px 18px 14px; }
	.tl-scroll { overflow-x: auto; }
	.tl-body { position: relative; min-width: 640px; }

	.tl-lines { position: absolute; inset: 22px 0 0 var(--tl-label, 190px); display: grid; grid-template-columns: repeat(12, 1fr); pointer-events: none; z-index: 0; }
	.tl-lines span { border-right: 1px solid var(--glass-border); opacity: 0.4; }
	.tl-lines span:last-child { border-right: 0; }

	.tl-axis, .tl-row { display: grid; grid-template-columns: var(--tl-label, 190px) repeat(12, 1fr); align-items: center; }
	.tl-axis { position: relative; z-index: 1; padding-bottom: 7px; border-bottom: 1px solid var(--glass-border); }
	.tl-axis span { font-size: 9px; font-weight: 800; letter-spacing: 0.1em; color: var(--text-dim); text-align: center; text-transform: uppercase; }
	.tl-axis .tl-axis-label { text-align: left; letter-spacing: 0.16em; }

	.tl-group { position: relative; z-index: 1; margin-top: 14px; }
	.tl-glabel { font-size: 10px; font-weight: 900; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; }
	.tl-glabel .c { color: var(--text-dim); font-weight: 600; letter-spacing: 0; }

	.tl-row { height: 22px; border-radius: 5px; }
	.tl-row:hover { background: var(--glass-bg-strong); }
	.tl-name {
		font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden;
		text-overflow: ellipsis; padding-right: 12px; display: flex; align-items: center;
	}
	.tl-name-dim { color: var(--text-dim); font-style: italic; }
	.tl-name-abandoned { color: var(--danger, #e0556b); gap: 5px; }
	.tl-chip { width: 7px; height: 7px; border-radius: 2px; margin-right: 7px; flex-shrink: 0; }

	/* Pista continua: las barras se colocan por dia del ano, no por celda de mes */
	.tl-track { grid-column: 2 / -1; position: relative; height: 22px; }
	.tl-bar { position: absolute; top: 50%; height: 7px; margin-top: -3.5px; border-radius: 3px; min-width: 3px; display: block; }
	.tl-dot { position: absolute; top: 50%; width: 7px; height: 7px; margin: -3.5px 0 0 -3.5px; border-radius: 50%; display: block; }
	.tl-dot-abandoned { border: 1px dashed var(--danger, #e0556b); }

	/* Cortado a media partida: misma textura que lo completado, pero con borde
	   discontinuo y un final irregular en vez de redondeado — se rompio ahi. */
	.tl-bar-abandoned { border: 1px dashed var(--danger, #e0556b); border-right: none; border-radius: 3px 0 0 3px; }
	.tl-bar-abandoned::before {
		content: ""; position: absolute; inset: 0; border-radius: inherit;
		background: repeating-linear-gradient(115deg, rgba(0,0,0,0) 0 3px, rgba(0,0,0,0.4) 3px 6px);
	}
	.tl-bar-abandoned::after {
		content: ""; position: absolute; top: -3px; bottom: -3px; right: -1px; width: 3px;
		background: var(--danger, #e0556b);
		clip-path: polygon(0 0, 100% 15%, 0 30%, 100% 45%, 0 60%, 100% 75%, 0 90%, 100% 100%, 0 100%);
	}

	/* Aun abierto: misma textura, sin rojo — se difumina en vez de cortarse,
	   con una punta que respira para marcar que sigue en marcha ahora mismo. */
	.tl-bar-progress {
		-webkit-mask-image: linear-gradient(to right, black 0%, black 78%, transparent 100%);
		        mask-image: linear-gradient(to right, black 0%, black 78%, transparent 100%);
	}
	.tl-bar-progress::before {
		content: ""; position: absolute; inset: 0; border-radius: inherit;
		background: repeating-linear-gradient(115deg, rgba(0,0,0,0) 0 3px, rgba(0,0,0,0.4) 3px 6px);
	}
	.tl-tip {
		position: absolute; top: 50%; width: 6px; height: 6px; margin: -3px 0 0 -3px;
		border-radius: 50%; display: block; animation: tlTipPulse 1.8s ease-in-out infinite;
	}
	@keyframes tlTipPulse {
		0%, 100% { opacity: 0.45; transform: scale(1); }
		50% { opacity: 1; transform: scale(1.5); }
	}
	@media (prefers-reduced-motion: reduce) {
		.tl-tip { animation: none; opacity: 0.85; }
	}

	.tl-tag {
		position: absolute; top: 50%; transform: translateY(-50%);
		font-size: 9px; font-weight: 800; letter-spacing: 0.03em;
		color: var(--text-dim); background: var(--glass-bg-strong);
		border: 1px solid var(--glass-border); padding: 2px 7px; border-radius: 999px;
		white-space: nowrap; pointer-events: none;
	}
	.tl-tag-abandoned {
		color: var(--danger, #e0556b);
		background: color-mix(in oklab, var(--danger, #e0556b) 12%, transparent);
		border-color: color-mix(in oklab, var(--danger, #e0556b) 35%, transparent);
	}

	.tl-dots { position: relative; height: 22px; grid-column: 2 / -1; }
	.tl-dots i { position: absolute; top: 50%; width: 6px; height: 6px; margin: -3px 0 0 -3px; border-radius: 50%; display: block; }

	.tl-ribbon { grid-column: 2 / -1; display: grid; grid-template-columns: repeat(12, 1fr); gap: 2px; height: 12px; }
	.tl-ribbon span { border-radius: 2px; }

	.tl-legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--glass-border); font-size: 10px; color: var(--text-dim); }
	.tl-legend span { display: flex; align-items: center; gap: 6px; }
	.tl-legend i { display: block; background: var(--text-dim); }
	.tl-legend .lg-bar { width: 14px; height: 6px; border-radius: 3px; }
	.tl-legend .lg-dot { width: 6px; height: 6px; border-radius: 50%; }
	.tl-legend .lg-abandon {
		width: 14px; height: 6px; border-radius: 3px;
		background: repeating-linear-gradient(115deg, var(--danger, #e0556b) 0 3px, rgba(224,85,107,0.3) 3px 6px);
	}
	.tl-legend .lg-progress {
		width: 14px; height: 6px; border-radius: 3px; background: var(--text-dim);
		-webkit-mask-image: linear-gradient(to right, black 55%, transparent 100%);
		        mask-image: linear-gradient(to right, black 55%, transparent 100%);
	}
	.tl-legend .lg-hint { color: var(--text-dim); opacity: 0.75; font-style: italic; }

	/* ── Explorar: minimapa + ventana arrastrable ────────────────────── */
	.mm-wrap { position: relative; z-index: 1; }
	.mm-caption {
		display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px 14px;
		font-size: 10.5px; color: var(--text-dim); margin-bottom: 8px;
	}
	.mm-caption b { color: var(--text); font-weight: 800; }

	.minimap {
		position: relative; height: 78px; background: var(--glass-bg-strong);
		border: 1px solid var(--glass-border); border-radius: 10px; overflow: hidden;
		touch-action: none; user-select: none;
	}
	.mm-months { position: absolute; inset: 0; display: grid; grid-template-columns: repeat(12, 1fr); pointer-events: none; }
	.mm-months span { border-right: 1px solid var(--glass-border); opacity: 0.5; }
	.mm-months span:last-child { border-right: 0; }

	.mm-bands { position: absolute; inset: 7px 0; display: flex; flex-direction: column; gap: 3px; }
	.mm-band { position: relative; flex: 1; }
	.mm-bar { position: absolute; top: 50%; height: 60%; margin-top: -30%; border-radius: 2px; opacity: 0.6; display: block; }
	.mm-bar-abandoned {
		opacity: 0.85;
		background: repeating-linear-gradient(115deg, var(--danger, #e0556b) 0 2px, rgba(224,85,107,0.35) 2px 4px) !important;
	}
	.mm-bar-progress { opacity: 0.9; }
	.mm-dot { position: absolute; top: 50%; width: 3px; height: 3px; margin: -1.5px 0 0 -1.5px; border-radius: 50%; opacity: 0.7; display: block; }

	.mm-window {
		position: absolute; top: 0; bottom: 0; background: rgba(139,127,240,0.18);
		border-left: 2px solid var(--primary); border-right: 2px solid var(--primary); cursor: grab;
	}
	.mm-window:active { cursor: grabbing; }
	.mm-handle { position: absolute; top: 0; bottom: 0; width: 16px; cursor: ew-resize; }
	.mm-handle.mm-handle-left { left: -9px; }
	.mm-handle.mm-handle-right { right: -9px; }

	.mm-axis { display: grid; grid-template-columns: repeat(12, 1fr); margin: 5px 0 12px; }
	.mm-axis span { font-size: 9px; font-weight: 800; color: var(--text-dim); text-align: center; letter-spacing: 0.08em; text-transform: uppercase; }

	.tl-explore-empty { padding: 30px 10px; text-align: center; color: var(--text-dim); font-size: 12px; font-style: italic; }

	.tl-explore-scroll { max-height: 420px; overflow-y: auto; position: relative; }
	.tl-explore-axis {
		position: sticky; top: 0; z-index: 2; background: var(--glass-bg);
		display: grid; grid-template-columns: var(--tl-label, 190px) repeat(12, 1fr);
		padding-bottom: 7px; border-bottom: 1px solid var(--glass-border);
	}
	.tl-explore-axis span { font-size: 9px; font-weight: 800; letter-spacing: 0.1em; color: var(--text-dim); text-align: center; text-transform: uppercase; }
	.tl-explore-axis .tl-axis-label { text-align: left; letter-spacing: 0.16em; }

	@media (max-width: 640px) {
		.tl-body { --tl-label: 120px; }
		.tl-lines { inset: 22px 0 0 120px; }
	}
</style>
