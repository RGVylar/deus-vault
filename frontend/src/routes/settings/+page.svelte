<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api';
	import { onMount } from 'svelte';

	let readingWpm = $state(200);
	let readingWordsPerPage = $state(300);
	let spotifyClientId = $state('');
	let spotifyClientSecret = $state('');
	let tmdbApiKey = $state('');
	let saved = $state(false);
	let showSpotifySecret = $state(false);
	let backfillState = $state<'idle' | 'running' | 'done' | 'error'>('idle');
	let backfillResult = $state<{updated: number; failed: number; total: number} | null>(null);
	let steamApiKey = $state('');
	let steamSyncState = $state<'idle' | 'syncing' | 'done' | 'error'>('idle');
	let steamSyncResult = $state<{synced: number; created: number; total_steam_games: number} | null>(null);

	// Reading speed test
	const TEST_TEXT = `El hábito de la lectura es una de las mejores costumbres que puede cultivar una persona. A través de los libros descubrimos mundos que jamás podríamos visitar, conocemos personas que nunca existieron pero que nos enseñan verdades eternas, y exploramos ideas que transforman nuestra manera de ver la realidad. Leer con regularidad mejora la concentración, amplía el vocabulario y desarrolla la capacidad de pensar con claridad. No importa el género ni el tema: cada libro abre una puerta hacia algo nuevo. Algunos prefieren la ficción porque les permite escapar de la rutina diaria; otros se inclinan por el ensayo o la divulgación científica porque satisface su curiosidad sobre el mundo. Lo que importa es encontrar aquello que te haga querer seguir leyendo, página tras página, sin importar la hora ni el lugar. La lectura nos hace más empáticos, porque nos obliga a ponernos en el lugar de otros, a entender sus miedos, sus alegrías y sus contradicciones. Un buen libro puede cambiar la perspectiva de una persona para siempre.`;
	const TEST_WORD_COUNT = TEST_TEXT.trim().split(/\s+/).length;

	let testPhase = $state<'idle' | 'reading' | 'result'>('idle');
	let testStartTime = $state<number | null>(null);
	let testResultWpm = $state<number | null>(null);
	let testElapsedSec = $state<number | null>(null);

	function startSpeedTest() {
		testPhase = 'reading';
		testStartTime = Date.now();
	}

	function stopSpeedTest() {
		if (!testStartTime) return;
		const elapsed = (Date.now() - testStartTime) / 1000;
		testElapsedSec = Math.round(elapsed);
		testResultWpm = Math.round(TEST_WORD_COUNT / (elapsed / 60));
		testPhase = 'result';
	}

	function applyTestWpm() {
		if (testResultWpm) readingWpm = testResultWpm;
		testPhase = 'idle';
	}

	function resetSpeedTest() {
		testPhase = 'idle';
		testStartTime = null;
		testResultWpm = null;
		testElapsedSec = null;
	}

	async function runTmdbBackfill(force = false) {
		backfillState = 'running';
		backfillResult = null;
		try {
			await api.post<any>(`/contents/backfill-tmdb-metadata${force ? '?force=true' : ''}`);
			backfillState = 'done';
		} catch (e: any) {
			backfillState = 'error';
			console.error('Backfill error:', e?.message ?? e);
		}
	}

	// Appearance
	let theme     = $state<'dark' | 'light'>('dark');
	let wallpaper = $state<'aurora' | 'atardecer' | 'oceano' | 'bosque'>('aurora');
	let blur      = $state(28);

	async function steamSync() {
		steamSyncState = 'syncing';
		steamSyncResult = null;
		try {
			const keyParam = steamApiKey ? `?steam_api_key=${encodeURIComponent(steamApiKey)}` : '';
			steamSyncResult = await api.post<{synced: number; created: number; total_steam_games: number}>(`/contents/steam/sync${keyParam}`);
			steamSyncState = 'done';
		} catch (e: any) {
			steamSyncState = 'error';
		}
	}

	async function steamDisconnect() {
		try {
			await api.del('/auth/steam/disconnect');
			auth.login(auth.token!, { ...auth.user!, steam_id: null });
		} catch (e: any) {}
	}

	onMount(async () => {
		if (!auth.isLoggedIn) goto('/login');

		// Tras el callback de Steam, refrescar datos del usuario
		const url = new URL(window.location.href);
		if (url.searchParams.get('steam') === 'connected') {
			try {
				const freshUser = await api.get<import('$lib/types').User>('/auth/me');
				auth.login(auth.token!, freshUser);
			} catch (e) {}
			url.searchParams.delete('steam');
			history.replaceState({}, '', url.toString());
		}

		try {
			const stored = localStorage.getItem('deus_vault_reading_wpm');
			if (stored) readingWpm = Number(stored) || 200;
			const storedPages = localStorage.getItem('deus_vault_words_per_page');
			if (storedPages) readingWordsPerPage = Number(storedPages) || 300;
			spotifyClientId = localStorage.getItem('deus_vault_spotify_client_id') || '';
			spotifyClientSecret = localStorage.getItem('deus_vault_spotify_client_secret') || '';
			tmdbApiKey = localStorage.getItem('deus_vault_tmdb_api_key') || '';
			steamApiKey = localStorage.getItem('deus_vault_steam_api_key') || '';
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
			if (steamApiKey.trim()) {
				localStorage.setItem('deus_vault_steam_api_key', steamApiKey.trim());
			} else {
				localStorage.removeItem('deus_vault_steam_api_key');
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

	<!-- Desktop topbar -->
	<div class="desk-topbar desk-only">
		<h1 class="desk-title">Ajustes</h1>
	</div>

	<!-- Mobile title -->
	<h1 class="mobile-only">Ajustes</h1>

	<div class="desk-settings-grid">

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
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px; border-bottom:none;">
			<span class="k">Prueba de velocidad lectora</span>
			{#if testPhase === 'idle'}
				<p class="muted" style="font-size:12px; margin:0;">Lee el texto a tu ritmo habitual y pulsa «Listo» al terminar. Se medirán las palabras por minuto.</p>
				<button class="btn" onclick={startSpeedTest} style="margin-top:4px;">▶ Iniciar prueba</button>
			{:else if testPhase === 'reading'}
				<div class="test-text">{TEST_TEXT}</div>
				<button class="btn btn-primary" onclick={stopSpeedTest} style="width:100%; justify-content:center;">✓ Listo, terminé de leer</button>
			{:else if testPhase === 'result'}
				<div class="test-result">
					<div class="test-result-wpm">{testResultWpm} <span>ppm</span></div>
					<div class="test-result-meta">
						{TEST_WORD_COUNT} palabras · {testElapsedSec}s
						{#if testResultWpm && testResultWpm < 100}
							· Lector lento (&lt; 100 ppm)
						{:else if testResultWpm && testResultWpm < 200}
							· Lector medio
						{:else if testResultWpm && testResultWpm < 350}
							· Lector rápido
						{:else}
							· Lector muy rápido
						{/if}
					</div>
				</div>
				<div style="display:flex; gap:8px; width:100%;">
					<button class="btn btn-primary" onclick={applyTestWpm} style="flex:1; justify-content:center;">Aplicar como velocidad</button>
					<button class="btn" onclick={resetSpeedTest}>Repetir</button>
				</div>
			{/if}
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

	<!-- Steam -->
	<div class="glass setting-group">
		<div class="setting-group-title">Steam</div>
		<div class="settings-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
			<span class="k">Steam API Key</span>
			<input class="text" type="password" bind:value={steamApiKey} placeholder="Tu API key de steamcommunity.com/dev/apikey" autocomplete="off" />
			<p class="muted" style="font-size:11px;">Se guarda localmente. Consíguela gratis en <strong>steamcommunity.com/dev/apikey</strong>.</p>
		</div>
		{#if auth.user?.steam_id}
			<div class="settings-row">
				<span class="k">Steam ID</span>
				<span class="v steam-id">{auth.user.steam_id}</span>
			</div>
			<div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;">
				<button
					class="btn btn-primary"
					onclick={steamSync}
					disabled={steamSyncState === 'syncing'}
					style="flex:1; justify-content:center;"
				>
					{steamSyncState === 'syncing' ? '⏳ Sincronizando…' : '🎮 Sincronizar tiempo jugado'}
				</button>
				<button class="btn" onclick={steamDisconnect} style="opacity:0.6; font-size:12px;">Desconectar</button>
			</div>
			{#if steamSyncState === 'done' && steamSyncResult}
				<p class="muted" style="font-size:12px; margin-top:8px; color:var(--game);">
					✅ {steamSyncResult.synced} juego{steamSyncResult.synced !== 1 ? 's' : ''} sincronizado{steamSyncResult.synced !== 1 ? 's' : ''}
					de {steamSyncResult.total_steam_games} en tu biblioteca Steam.
				</p>
			{:else if steamSyncState === 'error'}
				<p class="muted" style="font-size:12px; margin-top:8px; color:var(--red);">⚠ Error al sincronizar</p>
			{/if}
			<p class="muted" style="font-size:11px; margin-top:8px;">
				Actualiza la duración de los juegos del vault que tengan un <code>source_id</code> tipo <code>steam_APPID</code>
				con tu tiempo real de juego.
			</p>
		{:else}
			<p class="muted" style="font-size:13px; margin-bottom:12px;">
				Conecta tu cuenta de Steam para sincronizar el tiempo real de juego con los juegos del vault.
			</p>
			<button
				class="btn btn-primary"
				onclick={() => window.location.href = `/api/auth/steam/login?token=${auth.token}${steamApiKey ? '&steam_api_key=' + encodeURIComponent(steamApiKey) : ''}`}
			>
				🎮 Conectar con Steam
			</button>
			<p class="muted" style="font-size:11px; margin-top:10px;">
				Requiere <code>STEAM_API_KEY</code> configurada en el servidor y perfil de Steam público.
			</p>
		{/if}
	</div>

	<!-- Actions (save buttons — span full width on desktop) -->
	<div class="desk-settings-save glass setting-group" style="display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
		<button class="btn btn-primary" onclick={saveLocalSettings} style="flex:1; justify-content:center;">Guardar ajustes</button>
		<button class="btn" onclick={resetLocalSettings} style="flex:1; justify-content:center;">Restablecer lectura</button>
		{#if saved}
			<span style="color:var(--game); font-weight:600; font-size:13px; width:100%; text-align:center;">Guardado ✓</span>
		{/if}
	</div>

	</div><!-- /desk-settings-grid -->

	<!-- Sesión (full width on desktop) -->
	<div class="glass setting-group" style="margin-top:0;">
		<div class="setting-group-title">Sesión</div>
		<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
			<div>
				<div style="font-weight:700; font-size:15px;">{auth.user?.name}</div>
				<div class="muted" style="font-size:13px;">{auth.user?.email}</div>
			</div>
			<button class="btn btn-danger" onclick={logout} style="padding:10px 20px;">Cerrar sesión</button>
		</div>
	</div>

	<!-- Herramientas de mantenimiento -->
	<details class="glass setting-group" style="margin-top:0; cursor:pointer;">
		<summary style="font-size:13px; font-weight:700; color:var(--text-dim); letter-spacing:0.05em; list-style:none; display:flex; align-items:center; gap:6px; padding:2px 0;">
			<span>⚙️ Mantenimiento</span>
		</summary>
		<div style="margin-top:14px; display:flex; flex-direction:column; gap:10px;">
			<div style="font-size:12px; color:var(--text-muted); line-height:1.5;">
				Actualiza plataformas, trailer, géneros y fecha de estreno para todas las películas y series con ID de TMDB.
				Solo toca los que aún no tienen datos (sin <code>?force</code>).
			</div>
			<div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
				<button
					class="btn"
					onclick={() => runTmdbBackfill(false)}
					disabled={backfillState === 'running'}
				>
					{backfillState === 'running' ? '⏳ Actualizando…' : '🔄 Actualizar metadatos TMDB'}
				</button>
				<button
					class="btn"
					onclick={() => runTmdbBackfill(true)}
					disabled={backfillState === 'running'}
					style="opacity:0.6; font-size:11px;"
				>Forzar todo</button>
			</div>
			{#if backfillState === 'done'}
				<div style="font-size:12px; color:var(--green);">
					✅ Backfill iniciado en segundo plano — tardará ~30-60s. Recarga la bóveda cuando acabe.
				</div>
			{:else if backfillState === 'error'}
				<div style="font-size:12px; color:var(--red);">⚠ Error al ejecutar el backfill</div>
			{/if}
		</div>
	</details>

	<div class="center mt16" style="padding-bottom:8px;">
		<a href="https://ko-fi.com/Z8Z81OW7UV" target="_blank" rel="noopener noreferrer" class="btn" style="font-size:12px;">
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

	@media (min-width: 1024px) {
		.desk-settings-save { grid-column: 1 / -1; }
	}

	.test-text {
		background: var(--glass-bg-weak);
		border: 1px solid var(--glass-border);
		border-radius: 10px;
		padding: 14px 16px;
		font-size: 14px;
		line-height: 1.7;
		color: var(--text);
		width: 100%;
		box-sizing: border-box;
		user-select: none;
	}

	.test-result {
		width: 100%;
		background: var(--glass-bg-weak);
		border: 1px solid var(--glass-border);
		border-radius: 10px;
		padding: 14px 16px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}
	.test-result-wpm {
		font-size: 36px;
		font-weight: 800;
		color: var(--primary);
		line-height: 1;
	}
	.test-result-wpm span {
		font-size: 16px;
		font-weight: 600;
		color: var(--text-dim);
	}
	.test-result-meta {
		font-size: 12px;
		color: var(--text-muted);
		margin-top: 4px;
	}
</style>
