import { Capacitor } from '@capacitor/core';
import { auth } from '$lib/stores/auth.svelte';
import { translateApiError } from '$lib/i18n/apiErrors';

const BASE = Capacitor.isNativePlatform()
	? (import.meta.env.VITE_API_URL || 'https://vault.mugrelore.com/api')
	: '/api';

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = auth.token;
	if (token) headers['Authorization'] = `Bearer ${token}`;

	const res = await fetch(`${BASE}${path}`, { ...opts, headers: { ...headers, ...opts.headers } });

	if (res.status === 401) {
		auth.logout();
		throw new Error(translateApiError('Unauthorized'));
	}
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new Error(translateApiError(body.detail || res.statusText));
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

export const api = {
	get: <T>(path: string) => request<T>(path),
	post: <T>(path: string, body?: unknown) =>
		request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
	patch: <T>(path: string, body: unknown) =>
		request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
	del: <T>(path: string) => request<T>(path, { method: 'DELETE' })
};

export const wishlistApi = {
	list: (purchased?: boolean) => {
		const qs = purchased !== undefined ? `?purchased=${purchased}` : '';
		return api.get<import('./types').WishlistItem[]>(`/wishlist${qs}`);
	},
	stats: () => api.get<import('./types').WishlistStats>('/wishlist/stats'),
	lookup: (url: string) =>
		api.get<import('./types').ProductLookupResult>(`/wishlist/lookup?url=${encodeURIComponent(url)}`),
	create: (body: { title: string; url?: string | null; price?: number | null; image_url?: string | null; store?: string | null; notes?: string | null; source_id?: string | null }) =>
		api.post<import('./types').WishlistItem>('/wishlist', body),
	update: (id: number, body: Partial<{ title: string; url: string | null; price: number | null; image_url: string | null; store: string | null; notes: string | null }>) =>
		api.patch<import('./types').WishlistItem>(`/wishlist/${id}`, body),
	purchase: (id: number) => api.post<import('./types').WishlistItem>(`/wishlist/${id}/purchase`),
	unpurchase: (id: number) => api.post<import('./types').WishlistItem>(`/wishlist/${id}/unpurchase`),
	gift: (id: number) => api.post<import('./types').WishlistItem>(`/wishlist/${id}/gift`),
	ungift: (id: number) => api.post<import('./types').WishlistItem>(`/wishlist/${id}/ungift`),
	delete: (id: number) => api.del<void>(`/wishlist/${id}`),
};

export const distractionsApi = {
	stats: (days = 30) =>
		api.get<import('./types').DistractionStats>(`/distractions/stats?days=${days}`),
};
