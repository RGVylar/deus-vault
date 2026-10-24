import { t, type TKey } from './i18n/index.svelte';
import type { Component } from 'svelte';
import { BookOpen, Clapperboard, Gamepad2, LayoutGrid, Library, Music, Play, Tv } from '@lucide/svelte';

export function isLookupCandidate(url: string): boolean {
	try {
		const h = new URL(url).hostname.toLowerCase();
		return h.includes('youtube.com') || h.includes('youtu.be') ||
			h.includes('store.steampowered.com') || h.includes('netflix.com') ||
			h.includes('primevideo.com') || h.includes('amazon.com') ||
			h.includes('max.com') || h.includes('hbomax.com') ||
			h.includes('disneyplus.com') || h.includes('strem.io') ||
			h.includes('stremio.com') || h.includes('open.spotify.com') ||
			h.includes('crunchyroll.com') ||
			h.includes('openlibrary.org') || h.includes('goodreads.com') ||
			h.includes('books.google.com');
	} catch { return false; }
}

type ReleaseAware = { content_type: string; next_episode_date?: string | null; release_date?: string | null; coming_soon?: boolean };

/**
 * Año de estreno, cuando se puede saber.
 *
 * `release_date` es la columna propia; los items guardados antes de tenerla solo
 * lo saben en películas, donde `next_episode_date` guardaba el estreno de TMDB
 * (en series ese campo es el próximo episodio y no dice nada del año).
 */
export function releaseYear(c: ReleaseAware): number | null {
	const raw = c.release_date || (c.content_type === 'movie' ? c.next_episode_date : null);
	if (!raw) return null;
	const year = Number(String(raw).slice(0, 4));
	return Number.isFinite(year) && year >= 1900 && year <= 2100 ? year : null;
}

/**
 * Fecha de lanzamiento si todavía no ha llegado; `true` si está anunciado sin
 * fecha; `null` si ya ha salido o no se sabe. La comparación es con hoy, así que
 * la marca de "Próximamente" se quita sola el día del estreno.
 */
export function upcomingRelease(c: ReleaseAware): Date | true | null {
	if (c.release_date) {
		const d = new Date(c.release_date + 'T00:00:00');
		return d > new Date() ? d : null;
	}
	return c.coming_soon ? true : null;
}

export function formatDuration(minutes: number): string {
	if (minutes < 60) return `${minutes}min`;
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return m ? `${h}h ${m}m` : `${h}h`;
}

/** YouTube y Steam sirven imagen apaisada nativa (16:9 / 460x215); el resto son
 *  carteles verticales u otros que se recortarían mal en una caja panorámica. */
export function isLandscape(type: string): boolean {
	return type === 'youtube' || type === 'game';
}

/** Icono Lucide por tipo; para pintarlo, `<TypeIcon type={...} />`. */
export const TYPE_ICONS: Record<string, Component> = {
	all: LayoutGrid,
	youtube: Play,
	movie: Clapperboard,
	series: Tv,
	music: Music,
	book: BookOpen,
	manga: Library,
	game: Gamepad2
};

// Type accent colors matching CSS vars
export const TYPE_COLOR: Record<string, string> = {
	youtube: 'var(--youtube)',
	movie:   'var(--movie)',
	series:  'var(--series)',
	book:    'var(--book)',
	manga:   'var(--manga)',
	game:    'var(--game)',
	music:   'var(--music)',
};

export const PROVIDER_LABELS: Record<string, string> = {
	netflix: 'Netflix', prime: 'Prime Video', max: 'Max',
	disney: 'Disney+', crunchyroll: 'Crunchyroll', stremio: 'Stremio',
	appletv: 'Apple TV+',
};

// Reverse map: author string → provider key (for existing content without provider field)
const AUTHOR_TO_PROVIDER: Record<string, string> = {
	'Netflix': 'netflix', 'Prime Video': 'prime', 'Max': 'max',
	'Disney+': 'disney', 'Crunchyroll': 'crunchyroll', 'Stremio': 'stremio',
	'Apple TV+': 'appletv',
};

export function resolveProvider(c: { provider?: string | null; author?: string | null }): string | null {
	return c.provider ?? AUTHOR_TO_PROVIDER[c.author ?? ''] ?? null;
}

export function shortProviderName(name: string): string {
	const n = name.toLowerCase();
	if (n.includes('netflix')) return 'Netflix';
	if (n.includes('disney')) return 'D+';
	if (n.includes('prime') || (n.includes('amazon') && !n.includes('mgm'))) return 'Prime';
	if (n.includes('max') && !n.includes('starz')) return 'Max';
	if (n.includes('movistar')) return 'M+';
	if (n.includes('apple')) return 'Apple TV+';
	if (n.includes('crunchyroll')) return 'Crunchyroll';
	if (n.includes('skyshow')) return 'Sky';
	if (n.includes('rakuten')) return 'Rakuten';
	if (n.includes('filmin')) return 'Filmin';
	if (n.includes('mgm')) return 'MGM+';
	if (n.includes('starz')) return 'Starz';
	if (n.includes('mubi')) return 'Mubi';
	if (n.includes('paramount')) return 'Paramount+';
	if (n.includes('google play')) return 'G Play';
	if (n.includes('tivify')) return 'Tivify';
	// Fallback: first word, max 8 chars
	return name.split(' ')[0].substring(0, 8);
}

export function providerNameToKey(name: string): string {
	const n = name.toLowerCase();
	if (n.includes('netflix')) return 'netflix';
	if (n.includes('prime') || (n.includes('amazon') && !n.includes('mgm'))) return 'prime';
	if (n.includes('max') && !n.includes('starz')) return 'max';
	if (n.includes('disney')) return 'disney';
	if (n.includes('crunchyroll')) return 'crunchyroll';
	if (n.includes('apple')) return 'appletv';
	if (n.includes('movistar')) return 'movistar';
	if (n.includes('filmin')) return 'filmin';
	if (n.includes('skyshow')) return 'skyshowtime';
	if (n.includes('rakuten')) return 'rakuten';
	if (n.includes('starz')) return 'starz';
	if (n.includes('mgm')) return 'mgm';
	if (n.includes('mubi')) return 'mubi';
	if (n.includes('paramount')) return 'paramount';
	return 'other';
}

const TYPE_LABEL_KEYS: Record<string, TKey> = {
	all: 'types.all',
	youtube: 'types.youtube',
	movie: 'types.movie',
	series: 'types.series',
	music: 'types.music',
	book: 'types.book',
	manga: 'types.manga',
	game: 'types.game'
};

export function typeLabel(type: string): string {
	const key = TYPE_LABEL_KEYS[type];
	return key ? t(key) : type;
}

function isStremioUrl(url: string): boolean {
	return url.startsWith('stremio://') || url.includes('strem.io') || url.includes('stremio.com');
}

/** Marcador de capítulo en la URL guardada.
 *  `{n}` se sustituye por el capítulo/episodio/página que toca; `{nn}` y `{nnn}`
 *  hacen lo mismo rellenando con ceros a la izquierda (`{nnn}` → `007`).
 */
const CHAPTER_TOKEN = /\{(n+)\}/g;

export function hasChapterToken(url: string | null | undefined): boolean {
	return !!url && /\{n+\}/.test(url);
}

/** El número que toca abrir: lo leído + 1, sin pasarse del total conocido.
 *  En libros el total son páginas; en series y manga, episodios o capítulos. */
function nextUnit(content: ChapterAware): number {
	const done = Math.max(0, Math.floor(content.progress ?? 0));
	const total = content.content_type === 'book' ? content.page_count : content.episode_count;
	return total && total > 0 ? Math.min(done + 1, total) : done + 1;
}

type ChapterAware = {
	content_type: string;
	progress?: number | null;
	episode_count?: number | null;
	page_count?: number | null;
};

/** Rellena `{n}` en una URL con el capítulo por el que va el contenido.
 *  Si no hay marcador devuelve la URL tal cual. */
export function fillChapterToken(url: string, content: ChapterAware): string {
	if (!hasChapterToken(url)) return url;
	const n = nextUnit(content);
	return url.replace(CHAPTER_TOKEN, (_m, pad: string) => String(n).padStart(pad.length, '0'));
}

/** Build the best "open" URL for a content item.
 *  Priority: TMDB page > IMDb page > non-Stremio stored URL > YouTube > Steam > Stremio (last resort)
 */
export function buildConsumeUrl(content: ChapterAware & { url: string | null; source_id: string | null }): string | null {
	// TMDB source_id → TMDB page (much more useful than Stremio)
	if (content.source_id?.startsWith('tmdb:')) {
		const parts = content.source_id.split(':'); // tmdb:movie:12345 or tmdb:tv:12345
		if (parts.length === 3) {
			const mediaType = parts[1] === 'tv' ? 'tv' : 'movie';
			return `https://www.themoviedb.org/${mediaType}/${parts[2]}`;
		}
	}
	// IMDb ID (from Stremio lookups) → IMDb page
	if (content.source_id?.match(/^tt\d{7,}$/)) {
		return `https://www.imdb.com/title/${content.source_id}`;
	}
	// Stored URL — skip Stremio URLs, use everything else
	if (content.url && !isStremioUrl(content.url)) {
		return fillChapterToken(content.url, content);
	}
	// YouTube
	if (content.content_type === 'youtube' && content.source_id) {
		return `https://www.youtube.com/watch?v=${content.source_id}`;
	}
	// Steam
	if (content.content_type === 'game' && content.source_id) {
		return `steam://run/${content.source_id}`;
	}
	// Stremio as last resort (only if nothing else available)
	if (content.url && isStremioUrl(content.url)) return content.url;
	if (content.content_type === 'movie' && content.source_id) {
		return `stremio://detail/movie/${content.source_id}`;
	}
	if (content.content_type === 'series' && content.source_id) {
		return `stremio://detail/series/${content.source_id}`;
	}
	return null;
}

/** Build the TMDB URL for a content item if available (for refresh). */
export function buildTmdbRefreshUrl(content: { source_id: string | null; url: string | null }): string | null {
	if (content.source_id?.startsWith('tmdb:')) {
		const parts = content.source_id.split(':');
		if (parts.length === 3) {
			const mediaType = parts[1] === 'tv' ? 'tv' : 'movie';
			const tmdbId = parts[2];
			return `/lookup/tmdb-detail?tmdb_id=${tmdbId}&media_type=${mediaType}`;
		}
	}
	if (content.url && !isStremioUrl(content.url)) return null; // has a real URL, use /lookup/auto
	return null; // no good refresh path
}
