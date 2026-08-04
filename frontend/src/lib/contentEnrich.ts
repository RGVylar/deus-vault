/**
 * Lógica compartida para rellenar un item a partir de una URL: resolver metadatos
 * con /lookup/auto y traducirlos al payload de PATCH que espera /contents/{id}.
 *
 * La usan tres flujos distintos:
 *  - El modal "Añadir contenido" (guardado inmediato + pesca en segundo plano).
 *  - El botón ↻ de refrescar metadatos de un item ya guardado.
 *  - Pegar (Ctrl+V) una URL desde cualquier parte de la app, sin pasar por el modal.
 */

import { api } from './api';
import type { ContentType } from './types';

function readReadingPrefs(): { wpm: number; wordsPerPage: number } {
	try {
		const wpm = Number(localStorage.getItem('deus_vault_reading_wpm')) || 200;
		const wordsPerPage = Number(localStorage.getItem('deus_vault_words_per_page')) || 300;
		return { wpm, wordsPerPage };
	} catch {
		return { wpm: 200, wordsPerPage: 300 };
	}
}

/** Mejor esfuerzo antes de tener respuesta del backend — /lookup/auto puede corregirlo luego. */
export function guessTypeFromUrl(url: string): ContentType {
	if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
	if (url.includes('store.steampowered.com')) return 'game';
	return 'youtube';
}

export async function fetchAutoLookup(url: string): Promise<any> {
	const params = new URLSearchParams({ url });
	try {
		const tmdbKey = localStorage.getItem('deus_vault_tmdb_api_key');
		const spotifyId = localStorage.getItem('deus_vault_spotify_client_id');
		const spotifySecret = localStorage.getItem('deus_vault_spotify_client_secret');
		if (tmdbKey) params.set('tmdb_api_key', tmdbKey);
		if (spotifyId) params.set('spotify_client_id', spotifyId);
		if (spotifySecret) params.set('spotify_client_secret', spotifySecret);
	} catch { /* localStorage no disponible (SSR, modo privado…) */ }
	return api.get<any>(`/lookup/auto?${params.toString()}`);
}

/** Traduce la respuesta de /lookup/auto (o /lookup/tmdb-detail) a un payload de PATCH. */
export function buildEnrichPatch(data: any, currentType: string): Record<string, unknown> {
	const { wpm, wordsPerPage: defaultWordsPerPage } = readReadingPrefs();
	const type = data.suggested_content_type || currentType;
	const patch: Record<string, unknown> = {};

	if (type !== currentType) patch.content_type = type;
	if (data.title) patch.title = data.title;
	if (data.author) patch.author = data.author;
	if (data.thumbnail) patch.thumbnail = data.thumbnail;
	if (data.channel_thumbnail) patch.channel_thumbnail = data.channel_thumbnail;
	if (data.source_id) patch.source_id = data.source_id;
	if (data.provider) patch.provider = data.provider;
	if (data.trailer_url) patch.trailer_url = data.trailer_url;
	if (data.genres) patch.genres = data.genres;
	if (data.rating != null) patch.rating = data.rating;
	if (data.imdb_id) patch.imdb_id = data.imdb_id;

	if (type === 'book') {
		const pageCount = Number(data.page_count) || 0;
		if (pageCount > 0) {
			const wordsPerPage = Number(data.words_per_page) || defaultWordsPerPage;
			patch.page_count = pageCount;
			patch.words_per_page = wordsPerPage;
			patch.duration_minutes = Math.ceil(pageCount * wordsPerPage / Math.max(1, wpm));
		} else if (data.duration_minutes) {
			patch.duration_minutes = data.duration_minutes;
		}
	} else if (data.duration_minutes) {
		patch.duration_minutes = data.duration_minutes;
	}

	if (type === 'series') {
		if (data.episode_count != null) patch.episode_count = Number(data.episode_count);
		if (data.seasons != null) patch.seasons = Number(data.seasons);
		if (data.next_episode_date !== undefined) patch.next_episode_date = data.next_episode_date ?? null;
	}

	if (data.watch_providers?.length) {
		patch.streaming_providers = JSON.stringify(
			(data.watch_providers as Array<{ provider_name: string; type?: string }>).map((p) =>
				p.type === 'rent' || p.type === 'buy' ? '$' + p.provider_name : p.provider_name
			)
		);
	}

	return patch;
}

/**
 * Resuelve una URL y parchea el item ya creado con lo que encuentre.
 * Silenciosa a propósito: si falla, el item se queda con lo que tenía — el
 * botón ↻ de cada tarjeta sirve de reintento manual.
 */
export async function enrichContentInBackground(
	contentId: number,
	url: string,
	initialType: string,
	existingFetch?: Promise<any> | null
): Promise<boolean> {
	try {
		const data = existingFetch ? await existingFetch : await fetchAutoLookup(url);
		const patch = buildEnrichPatch(data, initialType);
		if (Object.keys(patch).length) {
			await api.patch(`/contents/${contentId}`, patch);
		}
		return true;
	} catch {
		return false;
	} finally {
		notifyContentAdded();
	}
}

/** Le dice a la página de la bóveda (si está montada) que recargue la lista. */
function notifyContentAdded() {
	try { window.dispatchEvent(new CustomEvent('deus_vault_content_added')); } catch { /* SSR */ }
}

/** Crea el item al instante con lo mínimo y lanza la pesca de metadatos en segundo plano. */
export async function createContentFromUrl(url: string): Promise<{ id: number } | null> {
	const type = guessTypeFromUrl(url);
	try {
		const created = await api.post<{ id: number }>('/contents', {
			title: '',
			content_type: type,
			url,
		});
		notifyContentAdded();
		if (created?.id) {
			void enrichContentInBackground(created.id, url, type);
		}
		return created;
	} catch {
		return null;
	}
}
