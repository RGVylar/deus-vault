/**
 * Cocina común de las imágenes de compartir: primitivas de canvas, la cabecera
 * de marca y el reparto entre compartir nativo y descarga.
 *
 * Vive aparte porque hay varias imágenes (el año, la timeline, el tiempo
 * perdido) y todas comparten formato, marca y forma de salir del navegador.
 */

export const TYPE_PALETTE: Record<string, string> = {
	youtube: '#e0556b',
	movie:   '#e8b84b',
	series:  '#7fc8e8',
	book:    '#7da8e8',
	game:    '#6fd49a',
	music:   '#d97fc8',
};
export const PRIMARY = '#c9a9f5';
export const PRIMARY_RGB = '168,120,230';

/** Story vertical (9:16) para Instagram/WhatsApp, o cuadrado (1:1) para feed. */
export type ShareFormat = 'story' | 'square';

/** 'shared': fue al menú nativo. 'downloaded': cayó a descarga. 'cancelled': el usuario cerró el menú. */
export type ShareResult = 'shared' | 'downloaded' | 'cancelled';

export interface Text { y: number; f: number }

export function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
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
export function fitText(ctx: CanvasRenderingContext2D, text: string, maxW: number): string {
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

/** Fondo degradado + halo superior, común a todas las imágenes. */
export function drawBackdrop(ctx: CanvasRenderingContext2D, W: number, H: number, glowY: number, glowR: number, glowAlpha = 0.28) {
	const g = ctx.createLinearGradient(0, 0, W, H);
	g.addColorStop(0, '#1a1030');
	g.addColorStop(0.5, '#120a24');
	g.addColorStop(1, '#0a0518');
	ctx.fillStyle = g;
	ctx.fillRect(0, 0, W, H);

	const rg = ctx.createRadialGradient(W / 2, glowY, 40, W / 2, glowY, glowR);
	rg.addColorStop(0, `rgba(${PRIMARY_RGB},${glowAlpha})`);
	rg.addColorStop(1, 'transparent');
	ctx.fillStyle = rg;
	ctx.fillRect(0, 0, W, H);
}

export interface BrandHeader { mark: Text; name: Text; tagline: Text; kicker: Text }

export function drawBrand(ctx: CanvasRenderingContext2D, W: number, h: BrandHeader, kicker: string) {
	ctx.textAlign = 'center';
	ctx.fillStyle = PRIMARY;
	ctx.font = `700 ${h.mark.f}px system-ui, sans-serif`;
	ctx.fillText('⛧', W / 2, h.mark.y);
	ctx.fillStyle = '#fff';
	ctx.font = `800 ${h.name.f}px system-ui, sans-serif`;
	ctx.fillText('DEUS VAULT', W / 2, h.name.y);
	ctx.fillStyle = 'rgba(255,255,255,0.5)';
	ctx.font = `italic ${h.tagline.f}px system-ui, sans-serif`;
	ctx.fillText('memento mori', W / 2, h.tagline.y);
	ctx.fillStyle = PRIMARY;
	ctx.font = `800 ${h.kicker.f}px system-ui, sans-serif`;
	ctx.fillText(kicker, W / 2, h.kicker.y);
}

export function drawFooter(ctx: CanvasRenderingContext2D, W: number, cfg: Text) {
	ctx.textAlign = 'center';
	ctx.fillStyle = 'rgba(255,255,255,0.3)';
	ctx.font = `600 ${cfg.f}px system-ui, sans-serif`;
	ctx.fillText('deus-vault', W / 2, cfg.y);
}

export function newCanvas(W: number, H: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
	const cv = document.createElement('canvas');
	cv.width = W; cv.height = H;
	const ctx = cv.getContext('2d');
	if (!ctx) throw new Error('canvas 2d context unavailable');
	return [cv, ctx];
}

export function toBlob(cv: HTMLCanvasElement): Promise<Blob> {
	return new Promise((resolve, reject) => {
		cv.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas toBlob returned null'))), 'image/png');
	});
}

export function download(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Ofrece la imagen al menú de compartir del sistema (móvil/PWA). Si no hay
 * compartir nativo — o falla — cae a descarga directa.
 */
export async function shareOrDownload(blob: Blob, filename: string, title: string): Promise<ShareResult> {
	const file = new File([blob], filename, { type: 'image/png' });
	if (navigator.canShare?.({ files: [file] })) {
		try {
			await navigator.share({ files: [file], title });
			return 'shared';
		} catch (e) {
			// El usuario cerró la hoja de compartir: no es un error, no descargamos a su espalda.
			if ((e as Error)?.name === 'AbortError') return 'cancelled';
		}
	}
	download(blob, filename);
	return 'downloaded';
}
