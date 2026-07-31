import type { DistractionRewind } from '$lib/types';
import { formatDuration } from '$lib/utils';
import { t, tc } from '$lib/i18n/index.svelte';
import {
	PRIMARY_RGB,
	drawBackdrop, drawBrand, drawFooter, fitText, newCanvas, roundRect, shareOrDownload, toBlob,
	type BrandHeader, type ShareFormat, type ShareResult, type Text,
} from '$lib/shareCanvas';

/** Cada plataforma con su color, para que la barra y la leyenda se entiendan. */
const PLATFORM_PALETTE: Record<string, string> = {
	shorts:  '#e0556b',
	tiktok:  '#e8b84b',
	twitter: '#7fc8e8',
	reels:   '#d97fc8',
};
const PLATFORM_LABEL: Record<string, string> = {
	shorts: 'Shorts',
	tiktok: 'TikTok',
	twitter: 'Twitter',
	reels: 'Reels',
};

interface WastedLayout {
	W: number; H: number; margin: number;
	glowY: number; glowR: number;
	brand: BrandHeader;
	kicker: Text; big: Text; sub: Text;
	barTop: number; barH: number;
	legend: Text; legendLineH: number;
	monthsLabel: Text; monthsTop: number; monthsH: number; axis: Text;
	statsTop: number; statH: number; statGap: number; statLabelF: number; statValueF: number;
	punch: Text; footer: Text;
}

const LAYOUTS: Record<ShareFormat, WastedLayout> = {
	story: {
		W: 1080, H: 1920, margin: 80,
		glowY: 420, glowR: 500,
		brand: { mark: { y: 118, f: 54 }, name: { y: 168, f: 34 }, tagline: { y: 198, f: 20 }, kicker: { y: 252, f: 26 } },
		kicker: { y: 348, f: 30 }, big: { y: 512, f: 148 }, sub: { y: 572, f: 30 },
		barTop: 660, barH: 34,
		legend: { y: 748, f: 22 }, legendLineH: 32,
		monthsLabel: { y: 872, f: 22 }, monthsTop: 900, monthsH: 280, axis: { y: 1222, f: 19 },
		statsTop: 1350, statH: 170, statGap: 24, statLabelF: 21, statValueF: 40,
		punch: { y: 1700, f: 34 }, footer: { y: 1866, f: 22 },
	},
	square: {
		W: 1080, H: 1080, margin: 70,
		glowY: 300, glowR: 380,
		brand: { mark: { y: 86, f: 40 }, name: { y: 128, f: 27 }, tagline: { y: 154, f: 17 }, kicker: { y: 198, f: 22 } },
		kicker: { y: 258, f: 24 }, big: { y: 372, f: 106 }, sub: { y: 418, f: 24 },
		barTop: 470, barH: 28,
		legend: { y: 542, f: 19 }, legendLineH: 28,
		monthsLabel: { y: 620, f: 19 }, monthsTop: 644, monthsH: 116, axis: { y: 790, f: 16 },
		statsTop: 816, statH: 104, statGap: 20, statLabelF: 18, statValueF: 30,
		punch: { y: 968, f: 24 }, footer: { y: 1048, f: 17 },
	},
};

/** Segundos a la forma corta que ya usa la app para los minutos. */
function fmtSeconds(seconds: number): string {
	return formatDuration(Math.round(seconds / 60));
}

/**
 * La imagen de lo perdido. El tono es de guasa a propósito: reírse de uno mismo
 * es lo que hace que alguien enseñe un dato que da vergüenza.
 */
function render(data: DistractionRewind, format: ShareFormat): HTMLCanvasElement {
	const L = LAYOUTS[format];
	const [cv, ctx] = newCanvas(L.W, L.H);
	const fullW = L.W - L.margin * 2;
	drawBackdrop(ctx, L.W, L.H, L.glowY, L.glowR, 0.24);
	drawBrand(ctx, L.W, L.brand, `REWIND ${data.year}`);

	ctx.textAlign = 'center';
	ctx.fillStyle = 'rgba(255,255,255,0.55)';
	ctx.font = `700 ${L.kicker.f}px system-ui, sans-serif`;
	ctx.fillText(t('wasted.share.kicker'), L.W / 2, L.kicker.y);

	ctx.fillStyle = '#fff';
	ctx.font = `900 ${L.big.f}px system-ui, sans-serif`;
	ctx.fillText(fmtSeconds(data.total_seconds), L.W / 2, L.big.y);
	ctx.fillStyle = 'rgba(255,255,255,0.7)';
	ctx.font = `600 ${L.sub.f}px system-ui, sans-serif`;
	ctx.fillText(tc('wasted.share.scrollingCount', data.total_items), L.W / 2, L.sub.y);

	// Reparto por plataforma
	const platforms = data.platforms.filter((p) => p.seconds > 0);
	if (platforms.length > 0) {
		const total = platforms.reduce((a, p) => a + p.seconds, 0);
		let x = L.margin;
		for (const p of platforms) {
			const w = (p.seconds / total) * fullW;
			ctx.fillStyle = PLATFORM_PALETTE[p.platform] ?? '#a878e6';
			roundRect(ctx, x, L.barTop, Math.max(w - 3, 4), L.barH, 10);
			ctx.fill();
			x += w;
		}

		// Leyenda: los colores no significan nada sin ella
		ctx.textAlign = 'left';
		const dot = Math.round(L.legend.f * 0.5);
		let lx = L.margin, line = 0;
		for (const p of platforms) {
			const label = `${PLATFORM_LABEL[p.platform] ?? p.platform} ${Math.round((p.seconds / total) * 100)}%`;
			ctx.font = `600 ${L.legend.f}px system-ui, sans-serif`;
			const w = dot + 10 + ctx.measureText(label).width;
			if (lx > L.margin && lx + w > L.margin + fullW) { line++; lx = L.margin; }
			const y = L.legend.y + line * L.legendLineH;
			ctx.fillStyle = PLATFORM_PALETTE[p.platform] ?? '#a878e6';
			ctx.beginPath();
			ctx.arc(lx + dot / 2, y - L.legend.f * 0.3, dot / 2, 0, Math.PI * 2);
			ctx.fill();
			ctx.fillStyle = 'rgba(255,255,255,0.7)';
			ctx.fillText(label, lx + dot + 10, y);
			lx += w + 26;
		}
	}

	// Mes a mes
	const maxMonth = Math.max(1, ...data.by_month);
	ctx.textAlign = 'left';
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = `700 ${L.monthsLabel.f}px system-ui, sans-serif`;
	ctx.fillText(t('wasted.share.monthByMonth'), L.margin, L.monthsLabel.y);
	const bw = fullW / 12;
	data.by_month.forEach((seconds, m) => {
		const h = Math.max(L.monthsH * (seconds / maxMonth), 3);
		ctx.fillStyle = `rgba(224,85,107,${(0.3 + 0.7 * (seconds / maxMonth)).toFixed(3)})`;
		roundRect(ctx, L.margin + m * bw + 4, L.monthsTop + L.monthsH - h, bw - 8, h, Math.min(8, h / 2));
		ctx.fill();
	});
	ctx.fillStyle = 'rgba(255,255,255,0.35)';
	ctx.font = `600 ${L.axis.f}px system-ui, sans-serif`;
	ctx.textAlign = 'center';
	const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'] as const;
	MONTHS.forEach((k, m) => {
		ctx.fillText(t(`common.month.${k}` as Parameters<typeof t>[0]), L.margin + (m + 0.5) * bw, L.axis.y);
	});

	// Tres datos que rematan
	const ratio = data.good_minutes > 0 ? data.total_seconds / 60 / data.good_minutes : null;
	const chips: [string, string][] = [
		[t('wasted.share.worstDay'), data.worst_day_seconds > 0 ? fmtSeconds(data.worst_day_seconds) : '—'],
		[t('wasted.share.daysScrolling'), tc('rewind.share.days', data.days_with_distraction)],
		[t('wasted.share.vsGood'), ratio != null ? `${Math.round(ratio * 100)}%` : '—'],
	];
	const cw = (fullW - L.statGap * 2) / 3;
	chips.forEach(([label, value], i) => {
		const x = L.margin + i * (cw + L.statGap);
		ctx.fillStyle = 'rgba(255,255,255,0.05)';
		roundRect(ctx, x, L.statsTop, cw, L.statH, 22);
		ctx.fill();
		ctx.strokeStyle = `rgba(${PRIMARY_RGB},0.22)`;
		ctx.lineWidth = 2;
		ctx.stroke();
		ctx.textAlign = 'center';
		ctx.fillStyle = 'rgba(255,255,255,0.45)';
		ctx.font = `700 ${L.statLabelF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, label.toUpperCase(), cw - 28), x + cw / 2, L.statsTop + L.statH * 0.36);
		ctx.fillStyle = '#fff';
		ctx.font = `800 ${L.statValueF}px system-ui, sans-serif`;
		ctx.fillText(fitText(ctx, value, cw - 28), x + cw / 2, L.statsTop + L.statH * 0.75);
	});

	// El remate con guasa, en dos líneas para que quepa
	ctx.textAlign = 'center';
	ctx.fillStyle = PRIMARY_RGB ? '#fff' : '#fff';
	ctx.font = `800 ${L.punch.f}px system-ui, sans-serif`;
	const days = Math.floor(data.total_seconds / 86400);
	const punch = days >= 1 ? tc('wasted.share.punchDays', days) : t('wasted.share.punchHours');
	ctx.fillText(fitText(ctx, punch, fullW), L.W / 2, L.punch.y);
	ctx.fillStyle = 'rgba(255,255,255,0.45)';
	ctx.font = `italic ${Math.round(L.punch.f * 0.72)}px system-ui, sans-serif`;
	ctx.fillText(t('wasted.share.punchSub'), L.W / 2, L.punch.y + L.punch.f + 12);

	drawFooter(ctx, L.W, L.footer);
	return cv;
}

/**
 * Genera la imagen del tiempo perdido y la ofrece al menú de compartir del
 * sistema; si no hay compartir nativo, cae a descarga.
 */
export async function exportWastedImage(data: DistractionRewind, format: ShareFormat = 'story'): Promise<ShareResult> {
	const blob = await toBlob(render(data, format));
	const filename = `deus-vault-perdido-${data.year}${format === 'square' ? '-feed' : ''}.png`;
	return shareOrDownload(blob, filename, `Deus Vault · ${data.year}`);
}
