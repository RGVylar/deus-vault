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

export function formatDuration(minutes: number): string {
	if (minutes < 60) return `${minutes}min`;
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return m ? `${h}h ${m}m` : `${h}h`;
}

export const TYPE_ICONS: Record<string, string> = {
	youtube: '▶️',
	movie: '🎬',
	series: '📺',
	music: '🎵',
	book: '📖',
	game: '🎮'
};

export const TYPE_LABELS: Record<string, string> = {
	youtube: 'YouTube',
	movie: 'Películas',
	series: 'Series',
	music: 'Música',
	book: 'Libro',
	game: 'Juego'
};

function isStremioUrl(url: string): boolean {
	return url.startsWith('stremio://') || url.includes('strem.io') || url.includes('stremio.com');
}

/** Build the best "open" URL for a content item.
 *  Priority: TMDB page > IMDb page > non-Stremio stored URL > YouTube > Steam > Stremio (last resort)
 */
export function buildConsumeUrl(content: { content_type: string; url: string | null; source_id: string | null }): string | null {
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
		return content.url;
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
