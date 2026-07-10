import { t, type TKey } from './index.svelte';

const EXACT: Record<string, TKey> = {
	'Unauthorized': 'errors.session',
	'Invalid token': 'errors.session',
	'Invalid credentials': 'errors.invalidCredentials',
	'Email already registered': 'errors.emailRegistered',
	'User not found': 'errors.userNotFound',
	'Admin access required': 'errors.adminRequired',
	'Content not found': 'errors.contentNotFound',
	'No pending content in that time range': 'errors.noPendingContent',
	'No encontrado': 'errors.notFound',
	'Steam API key no configurada': 'errors.steamApiKeyMissing',
	'Token inválido': 'errors.session',
	'Token de estado inválido': 'errors.invalidStateToken',
	'Usuario no encontrado': 'errors.userNotFound',
	'No se pudo extraer el Steam ID': 'errors.steamIdExtractFailed',
	'Cuenta de Steam no conectada': 'errors.steamNotConnected',
	'Spotify credentials not configured': 'errors.spotifyCredentialsMissing',
	'Failed to authenticate with Spotify API': 'errors.spotifyAuthFailed',
	'No access token from Spotify API': 'errors.spotifyNoToken',
	'Track not found on Spotify': 'errors.trackNotFound',
	'Unsupported book URL': 'errors.unsupportedBookUrl',
	'Video not found': 'errors.videoNotFound',
	'Invalid YouTube URL': 'errors.invalidYoutubeUrl',
	'Invalid Steam URL': 'errors.invalidSteamUrl',
	'Game not found': 'errors.gameNotFound',
	'Not found on TMDB': 'errors.tmdbNotFound',
	'TMDB API key required': 'errors.tmdbApiKeyRequired',
	'Unsupported streaming URL': 'errors.unsupportedStreamingUrl',
};

const PREFIX: Array<[string, TKey]> = [
	['Plataforma desconocida:', 'errors.unknownPlatform'],
	['Invalid Spotify track URL', 'errors.invalidSpotifyUrl'],
	['Verificación con Steam fallida', 'errors.steamVerifyFailed'],
	['Unsupported URL. Try YouTube', 'errors.unsupportedUrl'],
];

export function translateApiError(detail: string): string {
	const key = EXACT[detail] ?? PREFIX.find(([p]) => detail.startsWith(p))?.[1];
	return key ? t(key) : detail;
}
