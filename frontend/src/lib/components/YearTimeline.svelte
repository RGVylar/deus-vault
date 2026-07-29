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
	import { t, fmtDate as fmtDateI18n } from '$lib/i18n/index.svelte';
	import { formatDuration, typeLabel } from '$lib/utils';
	import Icon from './Icon.svelte';

	interface Props { items: Content[]; year: number; months: string[]; }
	let { items, year, months }: Props = $props();

	const CAMPAIGN: string[] = ['game', 'series', 'book'];
	const NOISE: string[] = ['youtube', 'music'];
	const COLORS: Record<string, string> = {
		youtube: 'var(--youtube)', movie: 'var(--movie)', series: 'var(--series)',
		book: 'var(--book)', game: 'var(--game)', music: 'var(--music)',
	};
	const LS_KEY = 'rw-timeline-view';

	let mixed = $state(false);
	onMount(() => {
		try { mixed = localStorage.getItem(LS_KEY) === 'mixed'; } catch { /* ignore */ }
	});
	function setView(m: boolean) {
		mixed = m;
		try { localStorage.setItem(LS_KEY, m ? 'mixed' : 'grouped'); } catch { /* ignore */ }
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

	type Bar = {
		id: number; title: string; type: string; color: string;
		startPct: number; endPct: number; hasSpan: boolean; minutes: number; when: string;
	};

	const bars = $derived.by<Bar[]>(() => {
		const out: Bar[] = [];
		for (const c of items) {
			if (!CAMPAIGN.includes(c.content_type)) continue;
			const end = yearPct(c.consumed_at);
			if (end === null) continue;
			const rawStart = yearPct(c.started_at);
			const hasSpan = rawStart !== null && rawStart < end;
			const mins = c.content_type === 'series' && c.episode_count
				? c.duration_minutes * c.episode_count
				: c.duration_minutes;
			out.push({
				id: c.id, title: c.title, type: c.content_type, color: COLORS[c.content_type],
				startPct: hasSpan ? (rawStart as number) : end, endPct: end, hasSpan, minutes: mins,
				when: c.consumed_at ? fmtDateI18n(new Date(c.consumed_at), { day: 'numeric', month: 'short' }) : '',
			});
		}
		return out;
	});

	/** Agrupadas por tipo (juego, serie, libro), cada grupo ordenado por inicio. */
	const grouped = $derived.by(() => {
		return CAMPAIGN
			.map(type => ({
				type,
				rows: bars.filter(b => b.type === type).sort((a, b) => a.startPct - b.startPct || b.endPct - a.endPct),
			}))
			.filter(g => g.rows.length > 0);
	});

	/** Todas revueltas, en orden cronológico de inicio. */
	const chrono = $derived([...bars].sort((a, b) => a.startPct - b.startPct || (b.endPct - b.startPct) - (a.endPct - a.startPct)));

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
	const hasAnything = $derived(bars.length > 0 || movies.length > 0 || noise.count > 0);
</script>

{#if hasAnything}
<section class="rewind-section">
	<h2>
		<span class="hico"><Icon name="activity" size={15} /></span>
		{t('rewind.yearTimeline')}
		<div class="tl-toggle" role="group" aria-label={t('rewind.timelineViewLabel')}>
			<button type="button" aria-pressed={!mixed} onclick={() => setView(false)}>{t('rewind.timelineGrouped')}</button>
			<button type="button" aria-pressed={mixed} onclick={() => setView(true)}>{t('rewind.timelineMixed')}</button>
		</div>
	</h2>

	<div class="surface tl-surface">
		<div class="tl-scroll">
			<div class="tl-body">
				<div class="tl-lines" aria-hidden="true">
					{#each months as _m}<span></span>{/each}
				</div>

				<div class="tl-axis">
					<span class="tl-axis-label">{t('rewind.timelineAxis')}</span>
					{#each months as m}<span>{m.slice(0, 1)}</span>{/each}
				</div>

				{#if mixed}
					<div class="tl-group">
						{#each chrono as b (b.id)}
							<div class="tl-row" title="{b.title} · {formatDuration(b.minutes)} · {b.when}">
								<span class="tl-name"><i class="tl-chip" style="background:{b.color}"></i>{b.title}</span>
								{#if b.hasSpan}
									<span class="tl-track"><i class="tl-bar" style="left:{b.startPct}%; width:{Math.max(b.endPct - b.startPct, 0.4)}%; background:{b.color}"></i></span>
								{:else}
									<span class="tl-track"><i class="tl-dot" style="left:{b.endPct}%; background:{b.color}"></i></span>
								{/if}
							</div>
						{/each}
					</div>
				{:else}
					{#each grouped as g (g.type)}
						<div class="tl-group">
							<div class="tl-glabel" style="color:{COLORS[g.type]}">
								{typeLabel(g.type)} <span class="c">{g.rows.length}</span>
							</div>
							{#each g.rows as b (b.id)}
								<div class="tl-row" title="{b.title} · {formatDuration(b.minutes)} · {b.when}">
									<span class="tl-name">{b.title}</span>
									{#if b.hasSpan}
										<span class="tl-track"><i class="tl-bar" style="left:{b.startPct}%; width:{Math.max(b.endPct - b.startPct, 0.4)}%; background:{b.color}"></i></span>
									{:else}
										<span class="tl-track"><i class="tl-dot" style="left:{b.endPct}%; background:{b.color}"></i></span>
									{/if}
								</div>
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
	.tl-chip { width: 7px; height: 7px; border-radius: 2px; margin-right: 7px; flex-shrink: 0; }

	/* Pista continua: las barras se colocan por dia del ano, no por celda de mes */
	.tl-track { grid-column: 2 / -1; position: relative; height: 22px; }
	.tl-bar { position: absolute; top: 50%; height: 7px; margin-top: -3.5px; border-radius: 3px; min-width: 3px; display: block; }
	.tl-dot { position: absolute; top: 50%; width: 7px; height: 7px; margin: -3.5px 0 0 -3.5px; border-radius: 50%; display: block; }

	.tl-dots { position: relative; height: 22px; grid-column: 2 / -1; }
	.tl-dots i { position: absolute; top: 50%; width: 6px; height: 6px; margin: -3px 0 0 -3px; border-radius: 50%; display: block; }

	.tl-ribbon { grid-column: 2 / -1; display: grid; grid-template-columns: repeat(12, 1fr); gap: 2px; height: 12px; }
	.tl-ribbon span { border-radius: 2px; }

	.tl-legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--glass-border); font-size: 10px; color: var(--text-dim); }
	.tl-legend span { display: flex; align-items: center; gap: 6px; }
	.tl-legend i { display: block; background: var(--text-dim); }
	.tl-legend .lg-bar { width: 14px; height: 6px; border-radius: 3px; }
	.tl-legend .lg-dot { width: 6px; height: 6px; border-radius: 50%; }
	.tl-legend .lg-hint { color: var(--text-dim); opacity: 0.75; font-style: italic; }

	@media (max-width: 640px) {
		.tl-body { --tl-label: 120px; }
		.tl-lines { inset: 22px 0 0 120px; }
	}
</style>
