<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';

	let readingWpm = $state(200);
	let readingWordsPerPage = $state(300);
	let spotifyClientId = $state('');
	let spotifyClientSecret = $state('');
	let tmdbApiKey = $state('');
	let saved = $state(false);
	let showSpotifySecret = $state(false);

	onMount(() => {
		if (!auth.isLoggedIn) goto('/login');
		try {
			const stored = localStorage.getItem('deus_vault_reading_wpm');
			if (stored) readingWpm = Number(stored) || 200;
			const storedPages = localStorage.getItem('deus_vault_words_per_page');
			if (storedPages) readingWordsPerPage = Number(storedPages) || 300;
			spotifyClientId = localStorage.getItem('deus_vault_spotify_client_id') || '';
			spotifyClientSecret = localStorage.getItem('deus_vault_spotify_client_secret') || '';
			tmdbApiKey = localStorage.getItem('deus_vault_tmdb_api_key') || '';
		} catch (e) {}
	});

	function logout() {
		auth.logout();
		goto('/login');
	}

	function dispatchSettingsChanged() {
		try {
			const ev = new CustomEvent('deus_vault_settings_changed', {
				detail: { readingWpm, readingWordsPerPage }
			});
			window.dispatchEvent(ev);
		} catch (e) {}
	}

	function saveLocalSettings() {
		try {
			localStorage.setItem('deus_vault_reading_wpm', String(readingWpm));
			localStorage.setItem('deus_vault_words_per_page', String(readingWordsPerPage));
			if (spotifyClientId.trim()) {
				localStorage.setItem('deus_vault_spotify_client_id', spotifyClientId.trim());
			} else {
				localStorage.removeItem('deus_vault_spotify_client_id');
			}
			if (spotifyClientSecret.trim()) {
				localStorage.setItem('deus_vault_spotify_client_secret', spotifyClientSecret.trim());
			} else {
				localStorage.removeItem('deus_vault_spotify_client_secret');
			}
			if (tmdbApiKey.trim()) {
				localStorage.setItem('deus_vault_tmdb_api_key', tmdbApiKey.trim());
			} else {
				localStorage.removeItem('deus_vault_tmdb_api_key');
			}
		} catch (e) {}
		dispatchSettingsChanged();
		saved = true;
		setTimeout(() => { saved = false; }, 2500);
	}

	function resetLocalSettings() {
		readingWpm = 200;
		readingWordsPerPage = 300;
		try {
			localStorage.removeItem('deus_vault_reading_wpm');
			localStorage.removeItem('deus_vault_words_per_page');
		} catch (e) {}
		dispatchSettingsChanged();
	}
</script>

{#if auth.isLoggedIn}
	<h1>Ajustes</h1>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.3rem;">Sesión</p>
		<p style="font-weight:600;">{auth.user?.name}</p>
		<p style="font-size:0.85rem; color:var(--text-muted);">{auth.user?.email}</p>
	</div>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.75rem;">Lectura</p>
		<label for="settings-wpm" style="display:block; font-weight:600; margin-bottom:0.25rem;">Velocidad de lectura (palabras/min)</label>
		<input id="settings-wpm" type="number" bind:value={readingWpm} min="50" max="2000" />
		<label for="settings-pages" style="display:block; font-weight:600; margin:0.75rem 0 0.25rem;">Palabras por página (promedio)</label>
		<input id="settings-pages" type="number" bind:value={readingWordsPerPage} min="50" max="1000" />
		<p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.5rem;">Se guardan localmente y se usan para estimar la duración de libros.</p>
	</div>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.75rem;">APIs externas</p>

		<label for="settings-tmdb" style="display:block; font-weight:600; margin-bottom:0.25rem;">TMDb API Key</label>
		<input id="settings-tmdb" type="password" bind:value={tmdbApiKey} placeholder="Tu API key de themoviedb.org" autocomplete="off" />
		<p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.25rem; margin-bottom:0.75rem;">
			Mejora la detección de películas y series desde Netflix, Prime, etc.
		</p>

		<label for="settings-spotify-id" style="display:block; font-weight:600; margin-bottom:0.25rem;">Spotify Client ID</label>
		<input id="settings-spotify-id" type="text" bind:value={spotifyClientId} placeholder="Client ID de tu app en Spotify Developers" autocomplete="off" />

		<label for="settings-spotify-secret" style="display:block; font-weight:600; margin:0.75rem 0 0.25rem;">Spotify Client Secret</label>
		<div style="display:flex; gap:0.5rem; align-items:center;">
			{#if showSpotifySecret}
				<input id="settings-spotify-secret" type="text" bind:value={spotifyClientSecret} placeholder="Client Secret" autocomplete="off" style="flex:1;" />
			{:else}
				<input id="settings-spotify-secret" type="password" bind:value={spotifyClientSecret} placeholder="Client Secret" autocomplete="off" style="flex:1;" />
			{/if}
			<button class="btn-secondary" onclick={() => showSpotifySecret = !showSpotifySecret} style="padding:0.4rem 0.6rem; white-space:nowrap;">
				{showSpotifySecret ? '🙈' : '👁'}
			</button>
		</div>
		<p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.25rem;">
			Necesario para detectar canciones de Spotify. Crea una app gratis en <strong>developer.spotify.com</strong>.
		</p>
	</div>

	<div style="display:flex; gap:0.5rem; margin-bottom:1.5rem; align-items:center;">
		<button onclick={saveLocalSettings} style="flex:1;">Guardar ajustes</button>
		<button class="btn-secondary" onclick={resetLocalSettings} style="flex:1;">Restablecer lectura</button>
		{#if saved}
			<span style="color:var(--game); margin-left:0.5rem; font-weight:600;">Guardado ✓</span>
		{/if}
	</div>

	<button class="btn-danger" onclick={logout} style="width:100%">Cerrar sesión</button>
{/if}
