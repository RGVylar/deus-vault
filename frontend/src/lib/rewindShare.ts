import type { RewindStats, TopItem } from '$lib/types';
import { fetchBlob } from '$lib/api';
import { formatDuration, typeLabel } from '$lib/utils';
import { t, tc } from '$lib/i18n/index.svelte';

const TYPE_PALETTE: Record<string, string> = {
	youtube: '#e0556b',
	movie:   '#e8b84b',
	series:  '#7fc8e8',
	book:    '#7da8e8',
	game:    '#6fd49a',
	music:   '#d97fc8',
};
const PRIMARY = '#c9a9f5';
const PRIMARY_RGB = '168,120,230';

/** Story vertical (9:16) para Instagram/WhatsApp, o cuadrado (1:1) para feed. */
export type ShareFormat = 'story' | 'square';

/** 'shared': fue al menú nativo. 'downloaded': cayó a descarga. 'cancelled': el usuario cerró el menú. */
export type ShareResult = 'shared' | 'downloaded' | 'cancelled';

interface Text { y: number; f: number }
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

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
	ctx.beginPath();
	ctx.moveTo(x + r, y);
	ctx.arcTo(x + w, y, x + w, y + h, r);
	ctx.arcTo(x + w, y + h, x, y + h, r);
	ctx.arcTo(x, y + h, x, y, r);
	ctx.arcTo(x, y, x + w, y, r);
	ctx.closePath();
}

/**
 * Recorta el texto para que quepa en `maxW`, cortando por palabra siempre que
 * eso no sacrifique más de un tercio de lo que cabría.
 */
function fitText(ctx: CanvasRenderingContext2D, text: string, maxW: number): string {
	if (ctx.measureText(text).width <= maxW) return text;
	let lo = 0, hi = text.length;
	while (lo < hi) {
		const mid = (lo + hi + 1) >> 1;
		if (ctx.measureText(text.slice(0, mid) + '…').width <= maxW) lo = mid; else hi = mid - 1;
	}
	let cut = text.slice(0, lo).trimEnd();
	const lastSpace = cut.lastIndexOf(' ');
	if (lastSpace > cut.length * 0.66) cut = cut.slice(0, lastSpace).trimEnd();
	return cut + '…';
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

	const channel = stats.top_youtube_channels[0];
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
	const cv = document.createElement('canvas');
	cv.width = L.W; cv.height = L.H;
	const ctx = cv.getContext('2d');
	if (!ctx) throw new Error('canvas 2d context unavailable');

	// Fondo
	const g = ctx.createLinearGradient(0, 0, L.W, L.H);
	g.addColorStop(0, '#1a1030');
	g.addColorStop(0.5, '#120a24');
	g.addColorStop(1, '#0a0518');
	ctx.fillStyle = g;
	ctx.fillRect(0, 0, L.W, L.H);

	const rg = ctx.createRadialGradient(L.W / 2, L.glowY, 40, L.W / 2, L.glowY, L.glowR);
	rg.addColorStop(0, `rgba(${PRIMARY_RGB},0.28)`);
	rg.addColorStop(1, 'transparent');
	ctx.fillStyle = rg;
	ctx.fillRect(0, 0, L.W, L.H);

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

function toBlob(cv: HTMLCanvasElement): Promise<Blob> {
	return new Promise((resolve, reject) => {
		cv.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas toBlob returned null'))), 'image/png');
	});
}

function download(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function buildBlob(stats: RewindStats, format: ShareFormat): Promise<Blob> {
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
export async function exportShareImage(stats: RewindStats, format: ShareFormat = 'story'): Promise<ShareResult> {
	const blob = await buildBlob(stats, format);
	const filename = `deus-vault-rewind-${stats.year}${format === 'square' ? '-feed' : ''}.png`;

	const file = new File([blob], filename, { type: 'image/png' });
	if (navigator.canShare?.({ files: [file] })) {
		try {
			await navigator.share({ files: [file], title: `Deus Vault · Rewind ${stats.year}` });
			return 'shared';
		} catch (e) {
			// El usuario cerró la hoja de compartir: no es un error, no descargamos a su espalda.
			if ((e as Error)?.name === 'AbortError') return 'cancelled';
		}
	}

	download(blob, filename);
	return 'downloaded';
}
