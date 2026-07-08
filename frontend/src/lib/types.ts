export interface User {
	id: number;
	email: string;
	name: string;
	steam_id: string | null;
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
	started_at: string | null;
	abandoned: boolean;
	abandoned_at: string | null;
	created_at: string;
	source_id: string | null;
	author: string | null;
	notes: string | null;
	progress?: number | null;
	pinned: boolean;
	collection: string | null;
	channel_thumbnail?: string | null;
	times_consumed?: number;
	next_episode_date?: string | null;
	rating?: number | null;
	provider?: string | null;
	trailer_url?: string | null;
	genres?: string | null;
	streaming_providers?: string | null;  // JSON: ["Netflix","Max"]
	imdb_id?: string | null;
}

/** Effective duration for stats/display: series multiply by episode count */
export function effectiveDuration(c: Content): number {
	if (c.content_type === 'series' && c.episode_count && c.episode_count > 0) {
		return c.duration_minutes * c.episode_count;
	}
	return c.duration_minutes;
}

export interface TypeStats {
	count: number;
	minutes: number;
}

export interface AbandonedTopItem {
	id: number;
	title: string;
	content_type: string;
	progress: number;
	duration_minutes: number;
	thumbnail: string | null;
	abandoned_at: string | null;
}

export interface VaultStats {
	total_pending_minutes: number;
	total_consumed_minutes: number;
	pending_count: number;
	consumed_count: number;
	abandoned_count: number;
	by_type: Record<string, number>;
	consumed_by_type: Record<string, TypeStats>;
	abandoned_minutes: number;
	abandoned_avg_pct: number | null;
	abandoned_top_items: AbandonedTopItem[];
	abandoned_by_type_rate: Record<string, number>;
	abandoned_stale_count: number;
}

export interface PaginatedContents {
	items: Content[];
	total: number;
	offset: number;
	limit: number;
}

export interface LookupResult {
	title: string;
	author: string;
	thumbnail: string;
	source_id: string;
	url: string;
	duration_minutes: number;
	next_episode_date?: string | null;
	watch_providers?: Array<{ provider_name: string; logo_path: string }>;
}

export interface TopItem {
	id: number;
	title: string;
	author: string | null;
	thumbnail: string | null;
	minutes: number;
}

export interface TopAuthor {
	name: string;
	count: number;
	minutes: number;
	thumbnail?: string | null;
}

export interface StreamingPlatform {
	name: string;
	count: number;
	minutes: number;
}

export interface TypeRewindStats {
	count: number;
	minutes: number;
	percentage_of_year: number;
}

export interface MonthStats {
	month: number;
	count: number;
	minutes: number;
}

export interface DayStats {
	count: number;
	minutes: number;
}

export interface MomentStats {
	week_start: string;
	week_end: string;
	minutes: number;
	count: number;
}

export interface WishlistItem {
	id: number;
	title: string;
	url: string | null;
	price: number | null;
	image_url: string | null;
	store: string | null;
	notes: string | null;
	source_id: string | null;
	purchased: boolean;
	purchased_at: string | null;
	gifted: boolean;
	created_at: string;
}

export interface WishlistStats {
	total_items: number;
	pending_items: number;
	purchased_items: number;
	gifted_items: number;
	total_cost: number;
	pending_cost: number;
	purchased_cost: number;
}

export interface ProductLookupResult {
	title: string | null;
	price: number | null;
	image_url: string | null;
	store: string | null;
	url: string | null;
	source_id: string | null;
	content_type_hint: string | null;
}

export interface RewindStats {
	year: number;
	total_consumed_minutes: number;
	total_consumed_count: number;
	percentage_of_year: number;
	by_type: Record<string, TypeRewindStats>;
	by_month: MonthStats[];
	calendar: Record<string, DayStats>;
	items: Content[];
	streak_max: number;
	streak_current: number;
	best_month: number | null;
	avg_days_to_consume: number | null;
	favorite_type: string | null;
	abandoned_count: number;
	abandoned_minutes: number;
	most_abandoned_type: string | null;
	completion_rate: number | null;
	top_youtube_channels: TopAuthor[];
	top_youtube_channels_by_count: TopAuthor[];
	top_youtube_genres: { genre: string; count: number; minutes: number }[];
	top_items_by_type: Record<string, TopItem[]>;
	streaming_breakdown: StreamingPlatform[];
	top_book_authors: TopAuthor[];
	by_hour: number[];
	by_day: number[];
	moment: MomentStats | null;
	avg_rating: number | null;
	prev_year_minutes: number;
	prev_year_count: number;
	best_rated_item:  { title: string; rating: number; content_type: string } | null;
	worst_rated_item: { title: string; rating: number; content_type: string } | null;
	epic_day_items: { title: string; content_type: string; duration_minutes: number }[];
}

// ── Distracciones (Bóveda de lo Perdido) ─────────────────────────────────

export interface PlatformTotal {
	platform: string;
	seconds: number;
	items_count: number;
}

export interface DistractionDay {
	date: string;
	platform: string;
	seconds: number;
	items_count: number;
}

export interface GoodDay {
	date: string;
	minutes: number;
}

export interface DistractionStats {
	today_seconds: number;
	week_seconds: number;
	month_seconds: number;
	total_seconds: number;
	total_items: number;
	platforms: PlatformTotal[];
	days: DistractionDay[];
	good_days: GoodDay[];
	good_today_minutes: number;
	good_week_minutes: number;
	good_month_minutes: number;
	good_total_minutes: number;
}
