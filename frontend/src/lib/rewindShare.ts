import type { RewindStats } from '$lib/types';
import { formatDuration } from '$lib/utils';

const TYPE_PALETTE: Record<string, string> = {
	youtube: '#e0556b',
	movie:   '#e8b84b',
	series:  '#7fc8e8',
	book:    '#7da8e8',
	game:    '#6fd49a',
	music:   '#d97fc8',
};

function minutesToDays(minutes: number): string {
	const d = Math.floor(minutes / (60 * 24));
	const h = Math.floor((minutes % (60 * 24)) / 60);
	if (d === 0) return `${h}h`;
	if (h === 0) return `${d} día${d !== 1 ? 's' : ''}`;
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
 * Renderiza una "story" 1080×1920 del Rewind en un canvas y dispara la descarga.
 * No depende del DOM de la página: pinta todo programáticamente con Canvas 2D.
 */
export function exportShareImage(stats: RewindStats): void {
	const W = 1080, H = 1920;
	const cv = document.createElement('canvas');
	cv.width = W; cv.height = H;
	const ctx = cv.getContext('2d');
	if (!ctx) return;

	// Fondo
	const g = ctx.createLinearGradient(0, 0, W, H);
	g.addColorStop(0, '#1a1030');
	g.addColorStop(0.5, '#120a24');
	g.addColorStop(1, '#0a0518');
	ctx.fillStyle = g;
	ctx.fillRect(0, 0, W, H);

	// Glow superior
	const rg = ctx.createRadialGradient(W / 2, 460, 40, W / 2, 460, 560);
	rg.addColorStop(0, 'rgba(168,120,230,0.28)');
	rg.addColorStop(1, 'transparent');
	ctx.fillStyle = rg;
	ctx.fillRect(0, 0, W, H);

	ctx.textAlign = 'center';

	// Marca
	ctx.fillStyle = '#c9a9f5';
	ctx.font = '700 64px system-ui, sans-serif';
	ctx.fillText('⛧', W / 2, 150);
	ctx.fillStyle = '#fff';
	ctx.font = '800 40px system-ui, sans-serif';
	ctx.fillText('DEUS VAULT', W / 2, 210);
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = 'italic 24px system-ui, sans-serif';
	ctx.fillText('memento mori', W / 2, 248);
	ctx.fillStyle = '#c9a9f5';
	ctx.font = '800 30px system-ui, sans-serif';
	ctx.fillText(`REWIND ${stats.year}`, W / 2, 330);

	// Número grande
	ctx.fillStyle = '#fff';
	ctx.font = '900 150px system-ui, sans-serif';
	ctx.fillText(formatDuration(stats.total_consumed_minutes), W / 2, 540);
	ctx.fillStyle = 'rgba(255,255,255,0.7)';
	ctx.font = '600 34px system-ui, sans-serif';
	ctx.fillText(`${stats.total_consumed_count} ítems · ${minutesToDays(stats.total_consumed_minutes)} de tu vida`, W / 2, 600);

	// 4 bloques de stats
	const topCh = stats.top_youtube_channels[0];
	const topSeries = stats.top_items_by_type['series']?.[0] ?? stats.top_items_by_type['movie']?.[0];
	const blocks: [string, string, string][] = [
		['Top canal', topCh?.name ?? '—', topCh ? formatDuration(topCh.minutes) : ''],
		['Top serie', topSeries?.title ?? '—', topSeries ? formatDuration(topSeries.minutes) : ''],
		['Racha máx.', `${stats.streak_max} días`, 'sin parar'],
		['Nota media', stats.avg_rating != null ? `${stats.avg_rating} / 10` : '—', stats.completion_rate != null ? `${stats.completion_rate}% completado` : ''],
	];
	const bx = 80, bw = (W - 160 - 40) / 2, bh = 220, gap = 40;
	blocks.forEach((b, i) => {
		const col = i % 2, row = Math.floor(i / 2);
		const x = bx + col * (bw + gap), y = 720 + row * (bh + gap);
		ctx.fillStyle = 'rgba(255,255,255,0.05)';
		roundRect(ctx, x, y, bw, bh, 28); ctx.fill();
		ctx.strokeStyle = 'rgba(168,120,230,0.25)'; ctx.lineWidth = 2; ctx.stroke();
		ctx.textAlign = 'left';
		ctx.fillStyle = 'rgba(255,255,255,0.45)';
		ctx.font = '700 24px system-ui, sans-serif';
		ctx.fillText(b[0].toUpperCase(), x + 36, y + 58);
		ctx.fillStyle = '#fff';
		ctx.font = '800 40px system-ui, sans-serif';
		let t = b[1];
		while (ctx.measureText(t).width > bw - 72 && t.length > 4) t = t.slice(0, -2);
		if (t !== b[1]) t = t.trim() + '…';
		ctx.fillText(t, x + 36, y + 118);
		ctx.fillStyle = '#c9a9f5';
		ctx.font = '600 28px system-ui, sans-serif';
		ctx.fillText(b[2], x + 36, y + 170);
		ctx.textAlign = 'center';
	});

	// Barra de reparto por tipo
	const dy = 1420;
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = '700 24px system-ui, sans-serif';
	ctx.textAlign = 'left';
	ctx.fillText('REPARTO POR TIPO', bx, dy);
	const typeTotal = Object.values(stats.by_type).reduce((a, t) => a + t.minutes, 0) || 1;
	const typeSorted = Object.entries(stats.by_type).sort((a, b) => b[1].minutes - a[1].minutes);
	let dx = bx; const dbw = W - 160;
	typeSorted.forEach(([type, s]) => {
		const w = s.minutes / typeTotal * dbw;
		ctx.fillStyle = TYPE_PALETTE[type] ?? '#a878e6';
		roundRect(ctx, dx, dy + 24, Math.max(w - 3, 4), 28, 8); ctx.fill();
		dx += w;
	});

	// Cierre
	ctx.textAlign = 'center';
	ctx.fillStyle = '#fff';
	ctx.font = '900 56px system-ui, sans-serif';
	ctx.fillText(`${stats.percentage_of_year.toFixed(2)}% de ${stats.year}`, W / 2, 1640);
	ctx.fillStyle = 'rgba(255,255,255,0.45)';
	ctx.font = 'italic 28px system-ui, sans-serif';
	ctx.fillText('¿valió la pena cada minuto?', W / 2, 1690);
	ctx.fillStyle = 'rgba(255,255,255,0.3)';
	ctx.font = '600 24px system-ui, sans-serif';
	ctx.fillText('deus-vault', W / 2, 1840);

	cv.toBlob((blob) => {
		if (!blob) return;
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `deus-vault-rewind-${stats.year}.png`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}, 'image/png');
}
