/**
 * Canales que pueden ocultarse de la interfaz.
 *
 * Al activar el filtro, los canales incluidos en esta lista desaparecen de
 * las listas y de sus vídeos asociados. Al desactivarlo, vuelven a mostrarse.
 *
 * El filtrado solo afecta a la visualización de canales y vídeos. Los datos
 * agregados (minutos totales, porcentajes, heatmap, etc.) permanecen sin
 * cambios para mantener la consistencia de las estadísticas.
 *
 * La configuración se guarda en localStorage, por lo que es independiente para
 * cada navegador y dispositivo.
 */

const LS_CHANNELS = 'deus_vault_hidden_channels';
const LS_ACTIVE = 'deus_vault_hide_channels_active';

function loadChannels(): string[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(LS_CHANNELS);
		const parsed = raw ? JSON.parse(raw) : [];
		return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : [];
	} catch {
		return [];
	}
}

export const privacy = $state({
	channels: loadChannels(),
	active: typeof localStorage !== 'undefined' && localStorage.getItem(LS_ACTIVE) === '1',
});

function persist() {
	try {
		localStorage.setItem(LS_CHANNELS, JSON.stringify(privacy.channels));
		localStorage.setItem(LS_ACTIVE, privacy.active ? '1' : '0');
	} catch { /* modo privado del navegador: se pierde al cerrar, no es grave */ }
}

/** Los nombres de canal llegan de fuentes distintas, así que comparo normalizado. */
function key(name: string): string {
	return name.trim().toLowerCase();
}

export function isMarked(name: string | null | undefined): boolean {
	if (!name) return false;
	const k = key(name);
	return privacy.channels.some((c) => key(c) === k);
}

export function toggleChannel(name: string) {
	const k = key(name);
	const i = privacy.channels.findIndex((c) => key(c) === k);
	if (i >= 0) privacy.channels.splice(i, 1);
	else privacy.channels.push(name);
	persist();
}

export function setActive(v: boolean) {
	privacy.active = v;
	persist();
}

/** True cuando el canal debe desaparecer ahora mismo. */
export function isHiddenNow(name: string | null | undefined): boolean {
	return privacy.active && isMarked(name);
}

/** Quita de una lista de canales los que estén ocultos ahora. */
export function filterChannels<T extends { name: string }>(list: T[]): T[] {
	if (!privacy.active || privacy.channels.length === 0) return list;
	return list.filter((c) => !isMarked(c.name));
}

/**
 * Quita los vídeos de canales ocultos. Sin esto el canal se cuela por la
 * puerta de atrás: desaparece de la lista de canales pero sus vídeos siguen
 * ahí con su título.
 */
export function filterYoutubeItems<T extends { content_type?: string; author?: string | null }>(items: T[]): T[] {
	if (!privacy.active || privacy.channels.length === 0) return items;
	return items.filter((c) => !(c.content_type === 'youtube' && isMarked(c.author)));
}
