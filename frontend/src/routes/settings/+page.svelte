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

	// Appearance
	let theme     = $state<'dark' | 'light'>('dark');
	let wallpaper = $state<'aurora' | 'atardecer' | 'oceano' | 'bosque'>('aurora');
	let blur      = $state(28);

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
			theme     = (localStorage.getItem('deus_vault_theme')     as any) || 'dark';
			wallpaper = (localStorage.getItem('deus_vault_wallpaper') as any) || 'aurora';
			blur      = Number(localStorage.getItem('deus_vault_blur')) || 28;
		} catch (e) {}
	});

	function applyAppearance() {
		try {
			localStorage.setItem('deus_vault_theme',     theme);
			localStorage.setItem('deus_vault_wallpaper', wallpaper);
			localStorage.setItem('deus_vault_blur',      String(blur));
		} catch (e) {}
		window.dispatchEvent(new CustomEvent('deus_vault_appearance_changed'));
	}

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

	<!-- Cuenta -->
	<div class="glass setting-group">
		<div class="setting-group-title">Cuenta</div>
		<div class="settings-row">
			<span class="k">Nombre</span>
			<span class="v">{auth.user?.name}</span>
		</div>
		<div class="settings-row">
			<span class="k">Email</span>
			<span class="v">{auth.user?.email}</span>
		</div>
	</div>

	<!-- Apariencia -->
	<div class="glass setting-group">
		<div class="setting-group-title">Apariencia</div>

		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Tema</span>
			<div class="seg" style="margin-bottom:0; width:100%;">
				<button class:active={theme === 'dark'}  onclick={() => { theme = 'dark';  applyAppearance(); }}>🌙 Oscuro</button>
				<button class:active={theme === 'light'} onclick={() => { theme = 'light'; applyAppearance(); }}>☀️ Claro</button>
			</div>
		</div>

		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Fondo</span>
			<div class="wallpaper-grid">
				{#each [
					{ id: 'aurora',    label: 'Aurora',    colors: ['#9b5de5','#00b4d8','#ff006e','#38b000'] },
					{ id: 'atardecer', label: 'Atardecer', colors: ['#ff6b35','#f7c59f','#e63946','#ff9f1c'] },
					{ id: 'oceano',    label: 'Océano',    colors: ['#0077b6','#00b4d8','#90e0ef','#48cae4'] },
					{ id: 'bosque',    label: 'Bosque',    colors: ['#2d6a4f','#52b788','#95d5b2','#1b4332'] },
				] as wp}
					<button
						class="wp-btn"
						class:wp-active={wallpaper === wp.id}
						onclick={() => { wallpaper = wp.id as any; applyAppearance(); }}
						title={wp.label}
					>
						<div class="wp-swatch">
							{#each wp.colors as c, i}
								<div style="background:{c}; border-radius:{i === 0 ? '8px 0 0 0' : i === 1 ? '0 8px 0 0' : i === 2 ? '0 0 0 8px' : '0 0 8px 0'};"></div>
							{/each}
						</div>
						<span>{wp.label}</span>
					</button>
				{/each}
			</div>
		</div>

		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:6px; border-bottom:none;">
			<span class="k">Desenfoque del cristal ({blur}px)</span>
			<input
				type="range" min="8" max="48" step="4"
				bind:value={blur}
				oninput={applyAppearance}
				style="width:100%; accent-color:var(--primary);"
			/>
		</div>
	</div>

	<!-- Lectura -->
	<div class="glass setting-group">
		<div class="setting-group-title">Lectura</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Velocidad de lectura (palabras/min)</span>
			<input id="settings-wpm" class="text" type="number" bind:value={readingWpm} min="50" max="2000" />
		</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Palabras por página (promedio)</span>
			<input id="settings-pages" class="text" type="number" bind:value={readingWordsPerPage} min="50" max="1000" />
		</div>
		<p class="muted" style="font-size:12px; margin-top:8px;">Se guardan localmente y se usan para estimar la duración de libros.</p>
	</div>

	<!-- APIs externas -->
	<div class="glass setting-group">
		<div class="setting-group-title">APIs externas</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">TMDb API Key</span>
			<input id="settings-tmdb" class="text" type="password" bind:value={tmdbApiKey} placeholder="Tu API key de themoviedb.org" autocomplete="off" />
			<p class="muted" style="font-size:11px;">Mejora la detección de películas y series desde Netflix, Prime, etc.</p>
		</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Spotify Client ID</span>
			<input id="settings-spotify-id" class="text" type="text" bind:value={spotifyClientId} placeholder="Client ID" autocomplete="off" />
		</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px; border-bottom:none;">
			<span class="k">Spotify Client Secret</span>
			<div class="row" style="width:100%;">
				{#if showSpotifySecret}
					<input id="settings-spotify-secret" class="text" type="text" bind:value={spotifyClientSecret} placeholder="Client Secret" autocomplete="off" style="flex:1;" />
				{:else}
					<input id="settings-spotify-secret" class="text" type="password" bind:value={spotifyClientSecret} placeholder="Client Secret" autocomplete="off" style="flex:1;" />
				{/if}
				<button class="btn" onclick={() => showSpotifySecret = !showSpotifySecret}>
					{showSpotifySecret ? '🙈' : '👁'}
				</button>
			</div>
			<p class="muted" style="font-size:11px;">Necesario para detectar canciones de Spotify. Crea una app gratis en <strong>developer.spotify.com</strong>.</p>
		</div>
	</div>

	<!-- Actions -->
	<div class="row mt8" style="flex-wrap:wrap; gap:8px; margin-bottom:20px;">
		<button class="btn btn-primary" onclick={saveLocalSettings} style="flex:1; justify-content:center;">Guardar ajustes</button>
		<button class="btn" onclick={resetLocalSettings} style="flex:1; justify-content:center;">Restablecer lectura</button>
		{#if saved}
			<span style="color:var(--game); font-weight:600; font-size:13px;">Guardado ✓</span>
		{/if}
	</div>

	<!-- Sesión -->
	<div class="glass setting-group">
		<div class="setting-group-title">Sesión</div>
		<button class="btn btn-danger" onclick={logout} style="width:100%; justify-content:center; padding:12px;">Cerrar sesión</button>
	</div>

	<div class="center mt16" style="padding-bottom:8px;">
		<a
			href="https://ko-fi.com/Z8Z81OW7UV"
			target="_blank"
			rel="noopener noreferrer"
			class="btn"
			style="font-size:12px;"
		>
			☕ Invítame una
		</a>
	</div>
{/if}

<style>
	.wallpaper-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 8px;
		width: 100%;
	}
	.wp-btn {
		all: unset;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		padding: 6px 4px;
		border-radius: 12px;
		border: 1px solid var(--glass-border);
		background: var(--glass-bg-weak);
		transition: border-color 0.15s, background 0.15s;
		font-size: 10px;
		color: var(--text-muted);
		font-family: inherit;
		font-weight: 600;
	}
	.wp-btn:hover { background: var(--glass-bg); }
	.wp-btn.wp-active {
		border-color: var(--glass-border-bright);
		background: var(--glass-bg);
		color: var(--text);
		box-shadow: 0 0 0 1px var(--primary);
	}
	.wp-swatch {
		width: 40px;
		height: 30px;
		border-radius: 8px;
		display: grid;
		grid-template-columns: 1fr 1fr;
		grid-template-rows: 1fr 1fr;
		overflow: hidden;
	}
	.wp-swatch div { width: 100%; height: 100%; }
</style>
