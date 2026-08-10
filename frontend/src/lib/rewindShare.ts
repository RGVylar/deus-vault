import type { Content, RewindStats, TopItem } from '$lib/types';
import { fetchBlob } from '$lib/api';
import { filterChannels, isHiddenNow } from '$lib/stores/privacy.svelte';
import { formatDuration, typeLabel } from '$lib/utils';
import { t, tc } from '$lib/i18n/index.svelte';

import {
	PRIMARY, PRIMARY_RGB, TYPE_PALETTE,
	drawBackdrop, fitText, newCanvas, roundRect, shareOrDownload, toBlob,
	type ShareFormat, type ShareResult, type Text,
} from '$lib/shareCanvas';

export type { ShareFormat, ShareResult };

/** 'year': el resumen de siempre. 'timeline': qué tenías entre manos y cuándo. */
export type ShareVariant = 'year' | 'timeline';
interface ChipsCfg { top: number; h: number; gap: number; count: number; labelF: number; valueF: number; subF: number }
interface RankCfg { top: number; rowH: number; gap: number; rows: number; thumb: number; rankF: number; titleF: number; subF: number; minF: number }
interface HeatCfg { top: number; gap: number; maxCell: number }
interface HoursCfg { top: number; h: number; gap: number }
interface LegendCfg { y: number; f: number; lineH: number; showPct: boolean }

interface Layout {
	W: number; H: number; margin: number;
	glowY: number; glowR: number;
	mark: Text; name: Text; tagline: Text; year: Text;
	big: Text; summary: Text;
	chips?: ChipsCfg;
	rankTitle?: Text; rank?: RankCfg;
	heatTitle?: Text; heat?: HeatCfg;
	hoursTitle?: Text; hours?: HoursCfg;
	breakdown: Text; barGap: number; barH: number; legend: LegendCfg;
	percent: Text; worthIt: Text; footer: Text;
}

const LAYOUTS: Record<ShareFormat, Layout> = {
	story: {
		W: 1080, H: 1920, margin: 80,
		glowY: 380, glowR: 520,
		mark:    { y: 118, f: 54 },
		name:    { y: 168, f: 34 },
		tagline: { y: 198, f: 20 },
		year:    { y: 252, f: 26 },
		big:     { y: 380, f: 128 },
		summary: { y: 428, f: 28 },
		chips: { top: 480, h: 110, gap: 20, count: 3, labelF: 20, valueF: 30, subF: 20 },
		rankTitle: { y: 650, f: 24 },
		rank: { top: 672, rowH: 82, gap: 12, rows: 5, thumb: 72, rankF: 34, titleF: 32, subF: 22, minF: 28 },
		heatTitle: { y: 1188, f: 24 },
		heat: { top: 1206, gap: 3, maxCell: 15 },
		hoursTitle: { y: 1370, f: 24 },
		hours: { top: 1388, h: 88, gap: 4 },
		breakdown: { y: 1556, f: 24 }, barGap: 24, barH: 28,
		legend: { y: 1646, f: 21, lineH: 30, showPct: true },
		percent: { y: 1740, f: 52 },
		worthIt: { y: 1792, f: 26 },
		footer:  { y: 1866, f: 22 },
	},
	square: {
		W: 1080, H: 1080, margin: 70,
		glowY: 280, glowR: 400,
		mark:    { y: 86,  f: 40 },
		name:    { y: 128, f: 27 },
		tagline: { y: 154, f: 17 },
		year:    { y: 198, f: 22 },
		big:     { y: 300, f: 92 },
		summary: { y: 344, f: 24 },
		rankTitle: { y: 396, f: 21 },
		rank: { top: 414, rowH: 76, gap: 10, rows: 3, thumb: 58, rankF: 27, titleF: 27, subF: 19, minF: 23 },
		heatTitle: { y: 714, f: 21 },
		heat: { top: 732, gap: 2, maxCell: 13 },
		breakdown: { y: 862, f: 21 }, barGap: 20, barH: 24,
		legend: { y: 936, f: 18, lineH: 25, showPct: false },
		percent: { y: 1006, f: 42 },
		worthIt: { y: 1044, f: 22 },
		footer:  { y: 1072, f: 17 },
	},
};

interface Chip { label: string; value: string; sub: string }
interface RankRow { title: string; sub: string; minutes: number; type: string; thumb: string | null }

function minutesToDays(minutes: number): string {
	const d = Math.floor(minutes / (60 * 24));
	const h = Math.floor((minutes % (60 * 24)) / 60);
	if (d === 0) return `${h}h`;
	if (h === 0) return tc('rewind.share.days', d);
	return `${d}d ${h}h`;
}

// ── Datos ────────────────────────────────────────────────────────────────

/**
 * Chips de cabecera: se eligen entre los datos que el usuario realmente tiene,
 * de más a menos interesante. Los que no aplican no se pintan.
 */
function buildChips(stats: RewindStats, count: number): Chip[] {
	const out: Chip[] = [];
	const add = (label: string, value: string | null | undefined, sub = '') => {
		if (value) out.push({ label, value, sub });
	};

	const channel = filterChannels(stats.top_youtube_channels)[0];
	if (channel) add(t('rewind.share.topChannel'), channel.name, formatDuration(channel.minutes));
	if (stats.streak_max > 0) add(t('rewind.share.maxStreak'), tc('rewind.share.streakDays', stats.streak_max), t('rewind.share.nonstop'));
	if (stats.avg_rating != null) {
		add(t('rewind.share.avgRating'), t('rewind.share.ratingOutOf', { rating: stats.avg_rating }),
			stats.completion_rate != null ? t('rewind.share.completedPct', { pct: stats.completion_rate }) : '');
	}

	const author = stats.top_book_authors[0];
	if (author) add(t('rewind.share.topAuthor'), author.name, formatDuration(author.minutes));
	const platform = stats.streaming_breakdown[0];
	if (platform) add(t('rewind.share.topPlatform'), platform.name, formatDuration(platform.minutes));
	if (stats.favorite_type) {
		add(t('rewind.share.favoriteType'), typeLabel(stats.favorite_type),
			formatDuration(stats.by_type[stats.favorite_type]?.minutes ?? 0));
	}
	if (stats.epic_day_count > 0) add(t('rewind.share.epicDay'), tc('rewind.share.epicItems', stats.epic_day_count), t('rewind.share.inOneDay'));
	if (stats.abandoned_count > 0) {
		add(t('rewind.share.abandoned'), tc('rewind.share.abandonedCount', stats.abandoned_count), formatDuration(stats.abandoned_minutes));
	}

	return out.slice(0, count);
}

/** Ranking global: los ítems que más tiempo se llevaron, mezclando todos los tipos. */
function buildRanking(stats: RewindStats, rows: number): RankRow[] {
	const all: RankRow[] = [];
	for (const [type, items] of Object.entries(stats.top_items_by_type)) {
		for (const it of items as TopItem[]) {
			// Un vídeo de un canal oculto lo delataría igual que la lista de canales.
			if (type === 'youtube' && isHiddenNow(it.author)) continue;
			all.push({
				title: it.title,
				sub: it.author ? `${typeLabel(type)} · ${it.author}` : typeLabel(type),
				minutes: it.minutes,
				type,
				thumb: it.thumbnail,
			});
		}
	}
	return all.sort((a, b) => b.minutes - a.minutes).slice(0, rows);
}

interface HeatCell { col: number; row: number; minutes: number }

/** Rejilla año-completo: una columna por semana, una fila por día de la semana. */
function buildHeat(stats: RewindStats): { cells: HeatCell[]; cols: number; max: number } {
	const jan1 = new Date(stats.year, 0, 1);
	const offset = (jan1.getDay() + 6) % 7; // lunes = 0
	const days = ((stats.year % 4 === 0 && stats.year % 100 !== 0) || stats.year % 400 === 0) ? 366 : 365;
	const cells: HeatCell[] = [];
	let max = 0;
	for (let i = 0; i < days; i++) {
		const d = new Date(stats.year, 0, 1 + i);
		const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
		const minutes = stats.calendar[key]?.minutes ?? 0;
		if (minutes > max) max = minutes;
		cells.push({ col: Math.floor((i + offset) / 7), row: (i + offset) % 7, minutes });
	}
	return { cells, cols: Math.floor((days - 1 + offset) / 7) + 1, max };
}

// ── Imágenes ─────────────────────────────────────────────────────────────

/**
 * Carga una miniatura sin contaminar el canvas: con `crossOrigin` un servidor
 * sin cabeceras CORS falla al cargar en vez de bloquear el `toBlob` después.
 * Cualquier fallo o tardanza devuelve null y se pinta un hueco de color.
 */
function loadImage(url: string, timeoutMs = 5000, anonymous = true): Promise<HTMLImageElement | null> {
	return new Promise((resolve) => {
		const img = new Image();
		if (anonymous) img.crossOrigin = 'anonymous';
		let settled = false;
		const done = (v: HTMLImageElement | null) => {
			if (settled) return;
			settled = true;
			img.onload = img.onerror = null;
			resolve(v);
		};
		const timer = setTimeout(() => done(null), timeoutMs);
		img.onload = () => { clearTimeout(timer); done(img); };
		img.onerror = () => { clearTimeout(timer); done(null); };
		img.src = url;
	});
}

/**
 * Segundo intento para los hosts que no mandan CORS: el backend sirve la
 * imagen desde nuestro dominio, y un blob: es mismo origen, así que entra al
 * canvas sin contaminarlo.
 */
async function loadViaProxy(url: string): Promise<HTMLImageElement | null> {
	let objectUrl: string | null = null;
	try {
		const blob = await fetchBlob(`/proxy/image?url=${encodeURIComponent(url)}`);
		objectUrl = URL.createObjectURL(blob);
		return await loadImage(objectUrl, 5000, false);
	} catch {
		return null;
	} finally {
		// Ya está decodificada en memoria: revocar ahora no afecta al drawImage.
		if (objectUrl) URL.revokeObjectURL(objectUrl);
	}
}

async function loadThumb(url: string): Promise<HTMLImageElement | null> {
	return (await loadImage(url)) ?? loadViaProxy(url);
}

async function loadThumbs(rows: RankRow[]): Promise<(HTMLImageElement | null)[]> {
	return Promise.all(rows.map((r) => (r.thumb ? loadThumb(r.thumb) : Promise.resolve(null))));
}

/**
 * Encaja la imagen dentro del hueco respetando su proporción y centrada. El
 * hueco mide siempre lo mismo (16:9) para que los títulos queden alineados,
 * pero la carátula no se recorta: una cabecera de Steam se ve entera y una
 * portada vertical de libro tampoco pierde nada.
 */
function drawFitted(ctx: CanvasRenderingContext2D, img: HTMLImageElement, x: number, y: number, w: number, h: number, r: number) {
	const s = Math.min(w / img.width, h / img.height);
	const dw = img.width * s, dh = img.height * s;
	const dx = x + (w - dw) / 2, dy = y + (h - dh) / 2;
	ctx.save();
	roundRect(ctx, dx, dy, dw, dh, Math.min(r, dw / 2, dh / 2));
	ctx.clip();
	ctx.drawImage(img, dx, dy, dw, dh);
	ctx.restore();
}

function drawThumbFallback(ctx: CanvasRenderingContext2D, row: RankRow, x: number, y: number, w: number, h: number, r: number) {
	const color = TYPE_PALETTE[row.type] ?? PRIMARY;
	ctx.fillStyle = color + '30';
	roundRect(ctx, x, y, w, h, r);
	ctx.fill();
	ctx.fillStyle = color;
	ctx.font = `800 ${Math.round(h * 0.44)}px system-ui, sans-serif`;
	ctx.textAlign = 'center';
	ctx.fillText(row.title.slice(0, 1).toUpperCase(), x + w / 2, y + h * 0.66);
	ctx.textAlign = 'left';
}

// ── Secciones ────────────────────────────────────────────────────────────

function sectionTitle(ctx: CanvasRenderingContext2D, L: Layout, cfg: Text, label: string) {
	ctx.textAlign = 'left';
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = `700 ${cfg.f}px system-ui, sans-serif`;
	ctx.fillText(label, L.margin, cfg.y);
}

function drawChips(ctx: CanvasRenderingContext2D, L: Layout, cfg: ChipsCfg, chips: Chip[]) {
	if (chips.length === 0) return;
	const fullW = L.W - L.margin * 2;
	const w = (fullW - cfg.gap * (chips.length - 1)) / chips.length;
	chips.forEach((c, i) => {
		const x = L.margin + i * (w + cfg.gap);
		ctx.fillStyle = 'rgba(255,255,255,0.05)';
		roundRect(ctx, x, cfg.top, w, cfg.h, 22);
		ctx.fill();
		ctx.strokeStyle = `rgba(${PRIMARY_RGB},0.25)`;
		ctx.lineWidth = 2;
		ctx.stroke();

		const tx = x + 24, maxW = w - 48;
		ctx.textAlign = 'left';
		ctx.fillStyle = 'rgba(255,255,255,0.45)';
		ctx.font = `700 ${cfg.labelF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, c.label.toUpperCase(), maxW), tx, cfg.top + 34);
		ctx.fillStyle = '#fff';
		ctx.font = `800 ${cfg.valueF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, c.value, maxW), tx, cfg.top + 74);
		if (c.sub) {
			ctx.fillStyle = PRIMARY;
			ctx.font = `600 ${cfg.subF}px system-ui, sans-serif`;
			ctx.fillText(fitText(ctx, c.sub, maxW), tx, cfg.top + 100);
		}
	});
}

function drawRanking(ctx: CanvasRenderingContext2D, L: Layout, cfg: RankCfg, rows: RankRow[], thumbs: (HTMLImageElement | null)[]) {
	const fullW = L.W - L.margin * 2;
	const max = rows[0]?.minutes || 1;
	rows.forEach((r, i) => {
		const y = cfg.top + i * (cfg.rowH + cfg.gap);
		const color = TYPE_PALETTE[r.type] ?? PRIMARY;

		// Fondo de la fila + relleno proporcional al tiempo: el ranking se lee de un vistazo.
		ctx.fillStyle = 'rgba(255,255,255,0.04)';
		roundRect(ctx, L.margin, y, fullW, cfg.rowH, 18);
		ctx.fill();
		ctx.save();
		roundRect(ctx, L.margin, y, fullW, cfg.rowH, 18);
		ctx.clip();
		ctx.fillStyle = color + '22';
		ctx.fillRect(L.margin, y, Math.max(fullW * (r.minutes / max), 4), cfg.rowH);
		ctx.restore();

		const pad = Math.round(cfg.rowH * 0.12);
		ctx.textAlign = 'center';
		ctx.fillStyle = 'rgba(255,255,255,0.35)';
		ctx.font = `900 ${cfg.rankF}px system-ui, sans-serif`;
		ctx.fillText(String(i + 1), L.margin + 32, y + cfg.rowH / 2 + cfg.rankF * 0.35);

		// Hueco 16:9: cabe cualquier carátula sin recortarla y no descuadra el texto.
		const slotW = Math.round(cfg.thumb * 16 / 9);
		const thumbX = L.margin + 56, thumbY = y + (cfg.rowH - cfg.thumb) / 2;
		const img = thumbs[i];
		if (img) drawFitted(ctx, img, thumbX, thumbY, slotW, cfg.thumb, 14);
		else drawThumbFallback(ctx, r, thumbX, thumbY, slotW, cfg.thumb, 14);

		// El tiempo se pinta primero para saber cuánto sitio le queda al título.
		ctx.textAlign = 'right';
		ctx.font = `800 ${cfg.minF}px system-ui, sans-serif`;
		const dur = formatDuration(r.minutes);
		const durW = ctx.measureText(dur).width;
		ctx.fillStyle = color;
		ctx.fillText(dur, L.margin + fullW - 24, y + cfg.rowH / 2 + cfg.minF * 0.35);

		const tx = thumbX + slotW + 20;
		const maxW = L.margin + fullW - 24 - durW - 24 - tx;
		ctx.textAlign = 'left';
		ctx.fillStyle = '#fff';
		ctx.font = `800 ${cfg.titleF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, r.title, maxW), tx, y + cfg.rowH / 2 - pad + 2);
		ctx.fillStyle = 'rgba(255,255,255,0.45)';
		ctx.font = `600 ${cfg.subF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, r.sub, maxW), tx, y + cfg.rowH / 2 + pad + cfg.subF);
	});
}

/** Punto de color + nombre del tipo, en filas que se parten solas si no caben. */
function drawTypeLegend(ctx: CanvasRenderingContext2D, L: Layout, entries: readonly (readonly [string, number])[]) {
	const cfg = L.legend;
	const fullW = L.W - L.margin * 2;
	const dot = Math.round(cfg.f * 0.5), gapDot = 10, gapItem = 26;

	ctx.font = `600 ${cfg.f}px system-ui, sans-serif`;
	ctx.textAlign = 'left';
	const labels = entries.map(([type, share]) => {
		const name = typeLabel(type);
		return cfg.showPct ? `${name} ${Math.round(share * 100)}%` : name;
	});

	let x = L.margin, line = 0;
	entries.forEach(([type], i) => {
		const w = dot + gapDot + ctx.measureText(labels[i]).width;
		if (x > L.margin && x + w > L.margin + fullW) {
			line++;
			x = L.margin;
		}
		const y = cfg.y + line * cfg.lineH;
		ctx.fillStyle = TYPE_PALETTE[type] ?? PRIMARY;
		ctx.beginPath();
		ctx.arc(x + dot / 2, y - cfg.f * 0.3, dot / 2, 0, Math.PI * 2);
		ctx.fill();
		ctx.fillStyle = 'rgba(255,255,255,0.7)';
		ctx.font = `600 ${cfg.f}px system-ui, sans-serif`;
		ctx.fillText(labels[i], x + dot + gapDot, y);
		x += w + gapItem;
	});
}

// ── Variante "entre manos" ───────────────────────────────────────────────

/**
 * Las campañas (juego, serie, libro) se viven durante semanas, así que van
 * como barras de inicio a fin. Las películas son de una sentada: un carril de
 * puntos. YouTube y música son cientos de ítems: una banda de intensidad
 * mensual. Mismo criterio que la línea de tiempo de la app.
 */
const TL_CAMPAIGN = ['game', 'series', 'manga', 'book'];
const TL_NOISE = ['youtube', 'music'];

interface TlBar { title: string; type: string; startPct: number; endPct: number; hasSpan: boolean; minutes: number }
interface TlData { bars: TlBar[]; hidden: number; movies: number[]; noise: number[]; noiseMax: number; totalCampaigns: number; totalMovies: number; months: number }

/**
 * Meses que ocupa el eje. En el año en curso se corta en el mes actual: si no,
 * un julio deja media imagen vacía y aplasta las barras en la mitad izquierda.
 */
function timelineMonths(year: number): number {
	const now = new Date();
	return year === now.getFullYear() ? now.getMonth() + 1 : 12;
}

/** Posición 0-1 dentro del tramo dibujado; null si la fecha cae fuera. */
function yearPct(iso: string | null | undefined, year: number, months: number): number | null {
	if (!iso) return null;
	const d = new Date(iso);
	if (isNaN(d.getTime()) || d.getFullYear() !== year) return null;
	const daysInMonth = new Date(year, d.getMonth() + 1, 0).getDate();
	const p = (d.getMonth() + (d.getDate() - 1) / daysInMonth) / months;
	return Math.min(1, Math.max(0, p));
}

function buildTimeline(stats: RewindStats, rows: number): TlData {
	const year = stats.year;
	const months = timelineMonths(year);
	const items = (stats.items ?? []) as Content[];

	const all: TlBar[] = [];
	for (const c of items) {
		if (!TL_CAMPAIGN.includes(c.content_type)) continue;
		const end = yearPct(c.consumed_at, year, months);
		if (end === null) continue;
		const rawStart = yearPct(c.started_at, year, months);
		const hasSpan = rawStart !== null && rawStart < end;
		const minutes = (c.content_type === 'series' || c.content_type === 'manga') && c.episode_count
			? c.duration_minutes * c.episode_count
			: c.duration_minutes;
		all.push({ title: c.title, type: c.content_type, startPct: hasSpan ? (rawStart as number) : end, endPct: end, hasSpan, minutes });
	}
	// Se eligen las más largas, pero se pintan en orden cronológico: así la
	// imagen se lee como el relato del año y no como un ranking.
	const picked = [...all].sort((a, b) => b.minutes - a.minutes).slice(0, rows);
	picked.sort((a, b) => a.startPct - b.startPct);

	const movies: number[] = [];
	for (const c of items) {
		if (c.content_type !== 'movie') continue;
		const p = yearPct(c.consumed_at, year, months);
		if (p !== null) movies.push(p);
	}

	const noise = new Array(months).fill(0);
	for (const c of items) {
		if (!TL_NOISE.includes(c.content_type)) continue;
		if (c.content_type === 'youtube' && isHiddenNow(c.author)) continue;
		const d = c.consumed_at ? new Date(c.consumed_at) : null;
		if (!d || isNaN(d.getTime()) || d.getFullYear() !== year || d.getMonth() >= months) continue;
		noise[d.getMonth()] += c.duration_minutes;
	}

	return {
		bars: picked,
		hidden: Math.max(0, all.length - picked.length),
		movies,
		noise,
		months,
		noiseMax: Math.max(1, ...noise),
		totalCampaigns: all.length,
		totalMovies: movies.length,
	};
}

interface TlLayout {
	W: number; H: number; margin: number;
	glowY: number; glowR: number;
	mark: Text; name: Text; tagline: Text; year: Text;
	title: Text; subtitle: Text;
	barsTop: number; rowStride: number; rows: number; barH: number; titleF: number;
	more: Text;
	moviesLabel: Text; moviesLane: number; dot: number;
	noiseLabel: Text; noiseTop: number; noiseH: number;
	axis: Text;
	legend: Text;
	percent: Text; worthIt: Text; footer: Text;
}

const TL_LAYOUTS: Record<ShareFormat, TlLayout> = {
	story: {
		W: 1080, H: 1920, margin: 80,
		glowY: 360, glowR: 480,
		mark: { y: 118, f: 54 }, name: { y: 168, f: 34 }, tagline: { y: 198, f: 20 }, year: { y: 252, f: 26 },
		title: { y: 344, f: 42 }, subtitle: { y: 390, f: 24 },
		barsTop: 470, rowStride: 96, rows: 6, barH: 26, titleF: 28,
		more: { y: 1076, f: 22 },
		moviesLabel: { y: 1152, f: 22 }, moviesLane: 1186, dot: 16,
		noiseLabel: { y: 1276, f: 22 }, noiseTop: 1298, noiseH: 126,
		axis: { y: 1462, f: 20 },
		legend: { y: 1530, f: 22 },
		percent: { y: 1672, f: 52 }, worthIt: { y: 1726, f: 26 }, footer: { y: 1866, f: 22 },
	},
	square: {
		W: 1080, H: 1080, margin: 70,
		glowY: 260, glowR: 380,
		mark: { y: 86, f: 40 }, name: { y: 128, f: 27 }, tagline: { y: 154, f: 17 }, year: { y: 198, f: 22 },
		title: { y: 262, f: 32 }, subtitle: { y: 298, f: 19 },
		barsTop: 344, rowStride: 64, rows: 4, barH: 20, titleF: 22,
		more: { y: 622, f: 18 },
		moviesLabel: { y: 674, f: 18 }, moviesLane: 700, dot: 12,
		noiseLabel: { y: 754, f: 18 }, noiseTop: 772, noiseH: 66,
		axis: { y: 864, f: 16 },
		legend: { y: 912, f: 18 },
		percent: { y: 982, f: 40 }, worthIt: { y: 1020, f: 21 }, footer: { y: 1058, f: 17 },
	},
};

function drawTimelineGrid(ctx: CanvasRenderingContext2D, L: TlLayout, top: number, bottom: number, months: number) {
	const fullW = L.W - L.margin * 2;
	ctx.strokeStyle = 'rgba(255,255,255,0.06)';
	ctx.lineWidth = 1;
	for (let m = 0; m <= months; m++) {
		const x = L.margin + (m / months) * fullW;
		ctx.beginPath();
		ctx.moveTo(x, top);
		ctx.lineTo(x, bottom);
		ctx.stroke();
	}
}

function renderTimeline(stats: RewindStats, format: ShareFormat): HTMLCanvasElement {
	const L = TL_LAYOUTS[format];
	const data = buildTimeline(stats, L.rows);
	const [cv, ctx] = newCanvas(L.W, L.H);
	const fullW = L.W - L.margin * 2;
	drawBackdrop(ctx, L.W, L.H, L.glowY, L.glowR, 0.26);

	// Marca
	ctx.textAlign = 'center';
	ctx.fillStyle = PRIMARY;
	ctx.font = `700 ${L.mark.f}px system-ui, sans-serif`;
	ctx.fillText('⛧', L.W / 2, L.mark.y);
	ctx.fillStyle = '#fff';
	ctx.font = `800 ${L.name.f}px system-ui, sans-serif`;
	ctx.fillText('DEUS VAULT', L.W / 2, L.name.y);
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = `italic ${L.tagline.f}px system-ui, sans-serif`;
	ctx.fillText('memento mori', L.W / 2, L.tagline.y);
	ctx.fillStyle = PRIMARY;
	ctx.font = `800 ${L.year.f}px system-ui, sans-serif`;
	ctx.fillText(`REWIND ${stats.year}`, L.W / 2, L.year.y);

	ctx.fillStyle = '#fff';
	ctx.font = `900 ${L.title.f}px system-ui, sans-serif`;
	ctx.fillText(t('rewind.share.timelineTitle'), L.W / 2, L.title.y);
	ctx.fillStyle = 'rgba(255,255,255,0.6)';
	ctx.font = `600 ${L.subtitle.f}px system-ui, sans-serif`;
	ctx.fillText(
		`${tc('rewind.share.campaignsCount', data.totalCampaigns)} · ${tc('rewind.share.moviesCount', data.totalMovies)}`,
		L.W / 2, L.subtitle.y,
	);

	// Rejilla de meses de fondo, para que las barras se sitúen en el año
	const gridBottom = L.noiseTop + L.noiseH;
	drawTimelineGrid(ctx, L, L.barsTop - 10, gridBottom, data.months);

	// Campañas
	ctx.textAlign = 'left';
	data.bars.forEach((b, i) => {
		const rowTop = L.barsTop + i * L.rowStride;
		ctx.fillStyle = '#fff';
		ctx.font = `800 ${L.titleF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, b.title, fullW - 160), L.margin, rowTop + L.titleF);

		const color = TYPE_PALETTE[b.type] ?? PRIMARY;
		const barY = rowTop + L.titleF + 14;
		const x = L.margin + b.startPct * fullW;
		// Sin started_at solo sabemos cuándo acabaste: se pinta una marca corta
		// en vez de inventar un tramo que no sabemos si existió.
		const w = b.hasSpan ? Math.max((b.endPct - b.startPct) * fullW, L.barH) : L.barH;
		ctx.fillStyle = color;
		roundRect(ctx, Math.min(x, L.margin + fullW - w), barY, w, L.barH, L.barH / 2);
		ctx.fill();

		ctx.fillStyle = 'rgba(255,255,255,0.5)';
		ctx.font = `600 ${Math.round(L.titleF * 0.7)}px system-ui, sans-serif`;
		ctx.textAlign = 'right';
		ctx.fillText(formatDuration(b.minutes), L.margin + fullW, rowTop + L.titleF);
		ctx.textAlign = 'left';
	});

	if (data.hidden > 0) {
		ctx.fillStyle = 'rgba(255,255,255,0.4)';
		ctx.font = `600 ${L.more.f}px system-ui, sans-serif`;
		ctx.fillText(tc('rewind.share.andMoreCampaigns', data.hidden), L.margin, L.more.y);
	}

	// Películas: una sentada cada una
	if (data.movies.length > 0) {
		ctx.fillStyle = 'rgba(255,255,255,0.5)';
		ctx.font = `700 ${L.moviesLabel.f}px system-ui, sans-serif`;
		ctx.fillText(t('rewind.share.moviesLane'), L.margin, L.moviesLabel.y);
		ctx.strokeStyle = 'rgba(255,255,255,0.12)';
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.moveTo(L.margin, L.moviesLane);
		ctx.lineTo(L.margin + fullW, L.moviesLane);
		ctx.stroke();
		ctx.fillStyle = TYPE_PALETTE.movie;
		for (const p of data.movies) {
			ctx.beginPath();
			ctx.arc(L.margin + p * fullW, L.moviesLane, L.dot / 2, 0, Math.PI * 2);
			ctx.fill();
		}
	}

	// Ruido: cientos de ítems, así que intensidad por mes
	if (data.noise.some((m) => m > 0)) {
		ctx.fillStyle = 'rgba(255,255,255,0.5)';
		ctx.font = `700 ${L.noiseLabel.f}px system-ui, sans-serif`;
		ctx.fillText(t('rewind.share.noiseLane'), L.margin, L.noiseLabel.y);
		const bw = fullW / data.months;
		data.noise.forEach((minutes, m) => {
			const h = Math.max(L.noiseH * (minutes / data.noiseMax), 3);
			ctx.fillStyle = `rgba(224,85,107,${(0.35 + 0.65 * (minutes / data.noiseMax)).toFixed(3)})`;
			roundRect(ctx, L.margin + m * bw + 3, L.noiseTop + L.noiseH - h, bw - 6, h, Math.min(6, h / 2));
			ctx.fill();
		});
	}

	// Eje de meses
	ctx.fillStyle = 'rgba(255,255,255,0.35)';
	ctx.font = `600 ${L.axis.f}px system-ui, sans-serif`;
	ctx.textAlign = 'center';
	const MONTH_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'] as const;
	MONTH_KEYS.slice(0, data.months).forEach((k, m) => {
		ctx.fillText(t(`common.month.${k}` as Parameters<typeof t>[0]), L.margin + (m + 0.5) * (fullW / data.months), L.axis.y);
	});

	// Leyenda: aquí el color es la única pista del tipo
	const usedTypes = [...new Set(data.bars.map((b) => b.type))];
	if (data.movies.length > 0) usedTypes.push('movie');
	if (data.noise.some((m) => m > 0)) usedTypes.push('youtube');
	drawTypeLegend(ctx, { W: L.W, margin: L.margin, legend: { y: L.legend.y, f: L.legend.f, lineH: L.legend.f + 10, showPct: false } } as Layout,
		usedTypes.map((type) => [type, 0] as const));

	// Cierre
	ctx.textAlign = 'center';
	ctx.fillStyle = '#fff';
	ctx.font = `900 ${L.percent.f}px system-ui, sans-serif`;
	ctx.fillText(formatDuration(stats.total_consumed_minutes), L.W / 2, L.percent.y);
	ctx.fillStyle = 'rgba(255,255,255,0.45)';
	ctx.font = `italic ${L.worthIt.f}px system-ui, sans-serif`;
	ctx.fillText(t('rewind.share.percentOfYear', { pct: stats.percentage_of_year.toFixed(2), year: stats.year }), L.W / 2, L.worthIt.y);
	ctx.fillStyle = 'rgba(255,255,255,0.3)';
	ctx.font = `600 ${L.footer.f}px system-ui, sans-serif`;
	ctx.fillText('deus-vault', L.W / 2, L.footer.y);

	return cv;
}

function drawHeatmap(ctx: CanvasRenderingContext2D, L: Layout, cfg: HeatCfg, stats: RewindStats) {
	const { cells, cols, max } = buildHeat(stats);
	const fullW = L.W - L.margin * 2;
	const cell = Math.min(cfg.maxCell, Math.floor((fullW - (cols - 1) * cfg.gap) / cols));
	const gridW = cols * (cell + cfg.gap) - cfg.gap;
	const x0 = L.margin + (fullW - gridW) / 2;
	const radius = Math.max(2, Math.round(cell * 0.28));

	for (const c of cells) {
		const x = x0 + c.col * (cell + cfg.gap);
		const y = cfg.top + c.row * (cell + cfg.gap);
		if (c.minutes > 0 && max > 0) {
			// Raíz cuadrada: si no, un día maratón aplasta visualmente al resto del año.
			const alpha = 0.22 + 0.78 * Math.sqrt(c.minutes / max);
			ctx.fillStyle = `rgba(${PRIMARY_RGB},${alpha.toFixed(3)})`;
		} else {
			ctx.fillStyle = 'rgba(255,255,255,0.05)';
		}
		roundRect(ctx, x, y, cell, cell, radius);
		ctx.fill();
	}
}

function drawHours(ctx: CanvasRenderingContext2D, L: Layout, cfg: HoursCfg, stats: RewindStats) {
	const fullW = L.W - L.margin * 2;
	const max = Math.max(...stats.by_hour, 1);
	const bw = (fullW - cfg.gap * 23) / 24;
	stats.by_hour.forEach((minutes, h) => {
		const x = L.margin + h * (bw + cfg.gap);
		const barH = Math.max(cfg.h * (minutes / max), 4);
		ctx.fillStyle = minutes > 0 ? `rgba(${PRIMARY_RGB},${(0.35 + 0.65 * (minutes / max)).toFixed(3)})` : 'rgba(255,255,255,0.06)';
		// El radio no puede pasar de la mitad del lado corto o la barra sale con forma de gancho.
		roundRect(ctx, x, cfg.top + cfg.h - barH, bw, barH, Math.min(8, bw / 2, barH / 2));
		ctx.fill();
	});
	// Referencias horarias bajo las barras.
	ctx.fillStyle = 'rgba(255,255,255,0.3)';
	ctx.font = '600 18px system-ui, sans-serif';
	ctx.textAlign = 'center';
	for (const h of [0, 6, 12, 18]) {
		ctx.fillText(`${h}h`, L.margin + h * (bw + cfg.gap) + bw / 2, cfg.top + cfg.h + 26);
	}
	ctx.textAlign = 'left';
}

// ── Render ───────────────────────────────────────────────────────────────

function renderCanvas(stats: RewindStats, format: ShareFormat, thumbs: (HTMLImageElement | null)[], rows: RankRow[]): HTMLCanvasElement {
	const L = LAYOUTS[format];
	const [cv, ctx] = newCanvas(L.W, L.H);
	drawBackdrop(ctx, L.W, L.H, L.glowY, L.glowR);

	// Marca
	ctx.textAlign = 'center';
	ctx.fillStyle = PRIMARY;
	ctx.font = `700 ${L.mark.f}px system-ui, sans-serif`;
	ctx.fillText('⛧', L.W / 2, L.mark.y);
	ctx.fillStyle = '#fff';
	ctx.font = `800 ${L.name.f}px system-ui, sans-serif`;
	ctx.fillText('DEUS VAULT', L.W / 2, L.name.y);
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = `italic ${L.tagline.f}px system-ui, sans-serif`;
	ctx.fillText('memento mori', L.W / 2, L.tagline.y);
	ctx.fillStyle = PRIMARY;
	ctx.font = `800 ${L.year.f}px system-ui, sans-serif`;
	ctx.fillText(`REWIND ${stats.year}`, L.W / 2, L.year.y);

	// Número grande
	ctx.fillStyle = '#fff';
	ctx.font = `900 ${L.big.f}px system-ui, sans-serif`;
	ctx.fillText(formatDuration(stats.total_consumed_minutes), L.W / 2, L.big.y);
	ctx.fillStyle = 'rgba(255,255,255,0.7)';
	ctx.font = `600 ${L.summary.f}px system-ui, sans-serif`;
	ctx.fillText(tc('rewind.share.summary', stats.total_consumed_count, { days: minutesToDays(stats.total_consumed_minutes) }), L.W / 2, L.summary.y);

	if (L.chips) drawChips(ctx, L, L.chips, buildChips(stats, L.chips.count));

	if (L.rank && L.rankTitle && rows.length > 0) {
		sectionTitle(ctx, L, L.rankTitle, t('rewind.share.ranking'));
		drawRanking(ctx, L, L.rank, rows, thumbs);
	}

	if (L.heat && L.heatTitle && Object.keys(stats.calendar).length > 0) {
		sectionTitle(ctx, L, L.heatTitle, t('rewind.share.heatmap'));
		drawHeatmap(ctx, L, L.heat, stats);
	}

	if (L.hours && L.hoursTitle && stats.by_hour.some((m) => m > 0)) {
		const peak = stats.by_hour.indexOf(Math.max(...stats.by_hour));
		sectionTitle(ctx, L, L.hoursTitle, t('rewind.share.peakHour', { hour: `${peak}:00` }));
		drawHours(ctx, L, L.hours, stats);
	}

	// Barra de reparto por tipo + leyenda: sin ella los colores no dicen nada.
	const typeSorted = Object.entries(stats.by_type).filter(([, s]) => s.minutes > 0).sort((a, b) => b[1].minutes - a[1].minutes);
	if (typeSorted.length > 0) {
		sectionTitle(ctx, L, L.breakdown, t('rewind.share.typeBreakdown'));
		const total = typeSorted.reduce((a, [, s]) => a + s.minutes, 0);
		const barW = L.W - L.margin * 2;
		let dx = L.margin;
		typeSorted.forEach(([type, s]) => {
			const w = s.minutes / total * barW;
			ctx.fillStyle = TYPE_PALETTE[type] ?? PRIMARY;
			roundRect(ctx, dx, L.breakdown.y + L.barGap, Math.max(w - 3, 4), L.barH, 8);
			ctx.fill();
			dx += w;
		});
		drawTypeLegend(ctx, L, typeSorted.map(([type, s]) => [type, s.minutes / total] as const));
	}

	// Cierre
	ctx.textAlign = 'center';
	ctx.fillStyle = '#fff';
	ctx.font = `900 ${L.percent.f}px system-ui, sans-serif`;
	ctx.fillText(t('rewind.share.percentOfYear', { pct: stats.percentage_of_year.toFixed(2), year: stats.year }), L.W / 2, L.percent.y);
	ctx.fillStyle = 'rgba(255,255,255,0.45)';
	ctx.font = `italic ${L.worthIt.f}px system-ui, sans-serif`;
	ctx.fillText(t('rewind.share.worthIt'), L.W / 2, L.worthIt.y);
	ctx.fillStyle = 'rgba(255,255,255,0.3)';
	ctx.font = `600 ${L.footer.f}px system-ui, sans-serif`;
	ctx.fillText('deus-vault', L.W / 2, L.footer.y);

	return cv;
}

async function buildBlob(stats: RewindStats, format: ShareFormat, variant: ShareVariant): Promise<Blob> {
	// La timeline se dibuja entera con datos que ya tenemos: no carga imágenes.
	if (variant === 'timeline') return toBlob(renderTimeline(stats, format));

	const rows = buildRanking(stats, LAYOUTS[format].rank?.rows ?? 0);
	const thumbs = await loadThumbs(rows);
	try {
		return await toBlob(renderCanvas(stats, format, thumbs, rows));
	} catch (e) {
		// Red de seguridad: si alguna miniatura contaminó el canvas pese al
		// crossOrigin, repetimos sin imágenes antes que quedarnos sin nada.
		if (!thumbs.some(Boolean)) throw e;
		return toBlob(renderCanvas(stats, format, thumbs.map(() => null), rows));
	}
}

/**
 * Genera la imagen del Rewind y la ofrece al menú de compartir del sistema
 * (móvil/PWA). Si no hay compartir nativo — o falla — cae a descarga directa.
 * Lanza si el canvas no se puede rasterizar; el llamante avisa al usuario.
 */
export async function exportShareImage(stats: RewindStats, format: ShareFormat = 'story', variant: ShareVariant = 'year'): Promise<ShareResult> {
	const blob = await buildBlob(stats, format, variant);
	const filename = `deus-vault-rewind-${stats.year}${variant === 'timeline' ? '-timeline' : ''}${format === 'square' ? '-feed' : ''}.png`;

	return shareOrDownload(blob, filename, `Deus Vault · Rewind ${stats.year}`);
}
