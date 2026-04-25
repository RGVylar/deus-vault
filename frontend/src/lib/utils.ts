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

export function buildConsumeUrl(content: { content_type: string; url: string | null; source_id: string | null }): string | null {
	if (content.url) return content.url;
	if (content.content_type === 'youtube' && content.source_id) {
		return `https://www.youtube.com/watch?v=${content.source_id}`;
	}
	if (content.content_type === 'game' && content.source_id) {
		return `steam://run/${content.source_id}`;
	}
	if (content.content_type === 'movie' && content.source_id) {
		return `stremio://detail/movie/${content.source_id}`;
	}
	if (content.content_type === 'series' && content.source_id) {
		return `stremio://detail/series/${content.source_id}`;
	}
	return null;
}
