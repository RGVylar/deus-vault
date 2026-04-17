export interface User {
	id: number;
	email: string;
	name: string;
}

export interface TokenResponse {
	access_token: string;
	user: User;
}

export type ContentType = 'youtube' | 'movie' | 'series' | 'book' | 'game' | 'music';

export interface Content {
	id: number;
	title: string;
	content_type: ContentType;
	url: string | null;
	thumbnail: string | null;
	duration_minutes: number;
	page_count?: number;
	words_per_page?: number;
	episode_count?: number | null;
	seasons?: number | null;
	consumed: boolean;
	consumed_at: string | null;
	created_at: string;
	source_id: string | null;
	author: string | null;
	notes: string | null;
}

/** Effective duration for stats/display: series multiply by episode count */
export function effectiveDuration(c: Content): number {
	if (c.content_type === 'series' && c.episode_count && c.episode_count > 0) {
		return c.duration_minutes * c.episode_count;
	}
	return c.duration_minutes;
}

export interface VaultStats {
	total_pending_minutes: number;
	total_consumed_minutes: number;
	pending_count: number;
	consumed_count: number;
	by_type: Record<string, number>;
}

export interface LookupResult {
	title: string;
	author: string;
	thumbnail: string;
	source_id: string;
	url: string;
	duration_minutes: number;
}
