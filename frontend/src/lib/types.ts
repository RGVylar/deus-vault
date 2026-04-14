export interface User {
	id: number;
	email: string;
	name: string;
}

export interface TokenResponse {
	access_token: string;
	user: User;
}

export type ContentType = 'youtube' | 'movie' | 'book' | 'game';

export interface Content {
	id: number;
	title: string;
	content_type: ContentType;
	url: string | null;
	thumbnail: string | null;
	duration_minutes: number;
	consumed: boolean;
	consumed_at: string | null;
	created_at: string;
	source_id: string | null;
	author: string | null;
	notes: string | null;
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
