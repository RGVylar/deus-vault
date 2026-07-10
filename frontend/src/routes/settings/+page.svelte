<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api';
	import { onMount } from 'svelte';
	import { t, tc, i18n, setLocale, fmtCurrency, type Locale, type TKey } from '$lib/i18n/index.svelte';

	const LANGUAGES: [Locale, string][] = [['es', '🇪🇸 Español'], ['en', '🇬🇧 English'], ['pt', '🇧🇷 Português']];

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

	// Bóveda de Deseos — salary
	let salaryAnnual = $state('');
	let salaryWeeklyHours = $state(40);
	let salaryCurrency = $state('EUR');
	let derivedHourlyRate = $derived(() => {
		const annual = parseFloat(salaryAnnual.replace(',', '.').replace(/\./g, '').replace(',', '.'));
		if (!annual || !salaryWeeklyHours) return null;
		return annual / (salaryWeeklyHours * 48);
	});

	// Reading speed test
	const testText = $derived(t('settings.reading.testText'));
	const testWordCount = $derived(testText.trim().split(/\s+/).length);

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
		testResultWpm = Math.round(testWordCount / (elapsed / 60));
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
			salaryAnnual = localStorage.getItem('deus_vault_salary_annual') || '';
			salaryWeeklyHours = Number(localStorage.getItem('deus_vault_salary_weekly_hours')) || 40;
			salaryCurrency = localStorage.getItem('deus_vault_salary_currency') || 'EUR';
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
			if (salaryAnnual.trim()) {
				localStorage.setItem('deus_vault_salary_annual', salaryAnnual.trim());
			} else {
				localStorage.removeItem('deus_vault_salary_annual');
			}
			localStorage.setItem('deus_vault_salary_weekly_hours', String(salaryWeeklyHours));
			localStorage.setItem('deus_vault_salary_currency', salaryCurrency);
			const hourly = derivedHourlyRate();
			if (hourly) {
				localStorage.setItem('deus_vault_hourly_rate', String(Math.round(hourly * 100) / 100));
			} else {
				localStorage.removeItem('deus_vault_hourly_rate');
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

	// Derived state for handoff
	const tmdbOk    = $derived(!!tmdbApiKey.trim());
	const spotifyOk = $derived(!!spotifyClientId.trim() && !!spotifyClientSecret.trim());
	const initial   = $derived((auth.user?.name?.charAt(0) ?? '?').toUpperCase());

	const wallpapers: { id: string; labelKey: TKey; colors: string[] }[] = [
		{ id: 'aurora',    labelKey: 'settings.appearance.wallpaper.aurora',    colors: ['#9b5de5','#00b4d8','#ff006e','#38b000'] },
		{ id: 'atardecer', labelKey: 'settings.appearance.wallpaper.atardecer', colors: ['#ff6b35','#f7c59f','#e63946','#ff9f1c'] },
		{ id: 'oceano',    labelKey: 'settings.appearance.wallpaper.oceano',    colors: ['#0077b6','#00b4d8','#90e0ef','#48cae4'] },
		{ id: 'bosque',    labelKey: 'settings.appearance.wallpaper.bosque',    colors: ['#2d6a4f','#52b788','#95d5b2','#1b4332'] },
	];
</script>

{#if auth.isLoggedIn}

	<!-- Mobile title -->
	<h1 class="cx-mtitle mobile-only">{t('settings.title')}</h1>

	<!-- Desktop topbar -->
	<div class="desk-topbar desk-only" style="margin-bottom:18px;">
		<div>
			<h1 class="desk-title">{t('settings.title')}</h1>
			<div class="cx-toptag">{t('settings.tagline')}</div>
		</div>
	</div>

	<!-- ── Identity header ── -->
	<div class="glass cx-head">
		<div class="cx-av">{initial}</div>
		<div class="cx-id">
			<div class="cx-kicker">{t('settings.yourAccount')}</div>
			<div class="cx-name">{auth.user?.name}</div>
			<div class="cx-email">{auth.user?.email}</div>
		</div>
		<div class="cx-brand">
			<div class="mk">⛧</div>
			<div class="tg">memento mori</div>
		</div>
	</div>

	<!-- ── Bento ── -->
	<div class="cx-grid">

		<!-- Apariencia (full width) -->
		<div class="glass cx-card cx-span2" style="--accent: var(--primary);">
			<div class="cx-card-head">
				<div class="cx-ico">🎨</div>
				<div class="cx-htxt">
					<div class="cx-title">{t('settings.appearance.title')}</div>
					<div class="cx-sub">{t('settings.appearance.subtitle')}</div>
				</div>
			</div>
			<div class="cx-body">
				<!-- Tema -->
				<div>
					<span class="cx-label">{t('settings.appearance.theme')}</span>
					<div class="cx-theme-row">
						<button class="cx-theme dark" class:on={theme === 'dark'} onclick={() => { theme = 'dark'; applyAppearance(); }}>
							<div class="cx-theme-prev"><div class="swatch"></div><div class="lines"><i></i><i></i><i></i></div></div>
							<div class="cx-theme-tag"><span>{t('settings.appearance.dark')}</span><span class="chk">✓</span></div>
						</button>
						<button class="cx-theme light" class:on={theme === 'light'} onclick={() => { theme = 'light'; applyAppearance(); }}>
							<div class="cx-theme-prev"><div class="swatch"></div><div class="lines"><i></i><i></i><i></i></div></div>
							<div class="cx-theme-tag"><span>{t('settings.appearance.light')}</span><span class="chk">✓</span></div>
						</button>
					</div>
				</div>

				<!-- Idioma -->
				<div>
					<span class="cx-label">{t('settings.appearance.language')}</span>
					<div style="display:flex; gap:8px;">
						{#each LANGUAGES as [code, label]}
							<button
								class="btn"
								class:btn-primary={i18n.locale === code}
								onclick={() => setLocale(code)}
								style="flex:1; justify-content:center; font-size:13px;"
							>{label}</button>
						{/each}
					</div>
				</div>

				<!-- Fondo -->
				<div>
					<span class="cx-label">{t('settings.appearance.background')}</span>
					<div class="cx-wp-grid">
						{#each wallpapers as wp}
							<button class="cx-wp" class:on={wallpaper === wp.id} onclick={() => { wallpaper = wp.id as any; applyAppearance(); }} title={t(wp.labelKey)}>
								<div class="cx-wp-sw">
									{#each wp.colors as c}
										<i style="background:{c};"></i>
									{/each}
									<span class="chk">✓</span>
								</div>
								<span>{t(wp.labelKey)}</span>
							</button>
						{/each}
					</div>
				</div>

				<!-- Blur -->
				<div>
					<span class="cx-label">{t('settings.appearance.blur')} · <span class="cx-blur-val">{blur}px</span></span>
					<div class="cx-blur">
						<input class="cx-range" type="range" min="8" max="48" step="4" bind:value={blur} oninput={applyAppearance} />
						<div class="cx-blur-demo"><div class="panel">glass</div></div>
					</div>
				</div>
			</div>
		</div>

		<!-- Lectura -->
		<div class="glass cx-card" style="--accent: var(--book);">
			<div class="cx-card-head">
				<div class="cx-ico">📖</div>
				<div class="cx-htxt">
					<div class="cx-title">{t('settings.reading.title')}</div>
					<div class="cx-sub">{t('settings.reading.subtitle')}</div>
				</div>
			</div>
			<div class="cx-body">
				<div class="cx-two">
					<div class="cx-field">
						<label for="cx-wpm">{t('settings.reading.speed')}</label>
						<div class="cx-input-unit">
							<input id="cx-wpm" class="text" type="number" bind:value={readingWpm} min="50" max="2000" />
							<span class="u">ppm</span>
						</div>
					</div>
					<div class="cx-field">
						<label for="cx-pages">{t('settings.reading.wordsPerPage')}</label>
						<div class="cx-input-unit">
							<input id="cx-pages" class="text" type="number" bind:value={readingWordsPerPage} min="50" max="1000" />
						</div>
					</div>
				</div>
				<!-- Prueba de velocidad -->
				<div class="cx-field">
					<span class="cx-label">{t('settings.reading.speedTest')}</span>
					{#if testPhase === 'idle'}
						<p class="cx-hint">{t('settings.reading.speedTestHint')}</p>
						<button class="btn" onclick={startSpeedTest} style="margin-top:4px;">{t('settings.reading.startTest')}</button>
					{:else if testPhase === 'reading'}
						<div class="cx-test-text">{testText}</div>
						<button class="btn btn-primary" onclick={stopSpeedTest} style="justify-content:center;">{t('settings.reading.doneReading')}</button>
					{:else if testPhase === 'result'}
						<div class="cx-test-result">
							<span class="cx-test-wpm">{testResultWpm}</span>
							<span class="cx-test-unit">ppm</span>
							<span class="cx-test-meta">
								{t('settings.reading.wordsCount', { count: testWordCount })} · {testElapsedSec}s ·
								{#if testResultWpm && testResultWpm < 100}{t('settings.reading.slow')}
								{:else if testResultWpm && testResultWpm < 200}{t('settings.reading.medium')}
								{:else if testResultWpm && testResultWpm < 350}{t('settings.reading.fast')}
								{:else}{t('settings.reading.veryFast')}{/if}
							</span>
						</div>
						<div style="display:flex; gap:8px;">
							<button class="btn btn-primary" onclick={applyTestWpm} style="flex:1; justify-content:center;">{t('settings.reading.applySpeed')}</button>
							<button class="btn" onclick={resetSpeedTest}>{t('settings.reading.repeat')}</button>
						</div>
					{/if}
				</div>
				<p class="cx-hint">{t('settings.reading.localOnly')}</p>
			</div>
		</div>

		<!-- Bóveda de Deseos — sueldo -->
		<div class="glass cx-card" id="salary" style="--accent: oklch(0.82 0.18 75);">
			<div class="cx-card-head">
				<div class="cx-ico">⭐</div>
				<div class="cx-htxt">
					<div class="cx-title">{t('settings.wishlist.title')}</div>
					<div class="cx-sub">{t('settings.wishlist.subtitle')}</div>
				</div>
			</div>
			<div class="cx-body">
				<div class="cx-two">
					<div class="cx-field">
						<label for="cx-salary">{t('settings.wishlist.annualSalary')}</label>
						<div class="cx-input-unit">
							<input id="cx-salary" class="text" type="text" placeholder="28000" bind:value={salaryAnnual} />
							<span class="u">{salaryCurrency === 'EUR' ? '€' : salaryCurrency === 'USD' ? '$' : '£'}</span>
						</div>
					</div>
					<div class="cx-field">
						<label for="cx-hours">{t('settings.wishlist.weeklyHours')}</label>
						<div class="cx-input-unit">
							<input id="cx-hours" class="text" type="number" min="1" max="80" bind:value={salaryWeeklyHours} />
							<span class="u">h</span>
						</div>
					</div>
				</div>
				<div class="cx-field">
					<label>{t('settings.wishlist.currency')}</label>
					<div style="display:flex; gap:8px;">
						{#each [['EUR','€ Euro'], ['USD','$ USD'], ['GBP','£ GBP']] as [code, label]}
							<button
								class="btn"
								class:btn-primary={salaryCurrency === code}
								onclick={() => salaryCurrency = code}
								style="flex:1; justify-content:center; font-size:13px;"
							>{label}</button>
						{/each}
					</div>
				</div>
				{#if derivedHourlyRate()}
					<div class="cx-salary-result">
						<span class="cx-salary-rate">
							{fmtCurrency(derivedHourlyRate()!, salaryCurrency, { maximumFractionDigits: 2 })}/h
						</span>
						<span class="cx-salary-label">{t('settings.wishlist.basedOn', { hours: salaryWeeklyHours })}</span>
					</div>
				{/if}
				<p class="cx-hint">{t('settings.wishlist.privacyHint')}</p>
			</div>
		</div>

		<!-- APIs externas -->
		<div class="glass cx-card" style="--accent: var(--movie);">
			<div class="cx-card-head">
				<div class="cx-ico">🔌</div>
				<div class="cx-htxt">
					<div class="cx-title">{t('settings.apis.title')}</div>
					<div class="cx-sub">{t('settings.apis.subtitle')}</div>
				</div>
			</div>
			<div class="cx-body">
				<div class="cx-api" style="--g: var(--movie);">
					<div class="cx-api-top">
						<div class="cx-api-glyph">T</div>
						<div class="cx-api-name">TMDb</div>
						<span class="cx-dot" class:ok={tmdbOk}>{tmdbOk ? t('settings.apis.configured') : t('settings.apis.notConfigured')}</span>
					</div>
					<input class="text" type="password" bind:value={tmdbApiKey} placeholder={t('settings.apis.tmdbPlaceholder')} autocomplete="off" />
				</div>
				<div class="cx-api" style="--g: var(--music);">
					<div class="cx-api-top">
						<div class="cx-api-glyph">S</div>
						<div class="cx-api-name">Spotify</div>
						<span class="cx-dot" class:ok={spotifyOk}>{spotifyOk ? t('settings.apis.configured') : t('settings.apis.notConfigured')}</span>
					</div>
					<input class="text" type="text" bind:value={spotifyClientId} placeholder={t('settings.apis.spotifyClientId')} autocomplete="off" />
					<div class="cx-pwrow">
						{#if showSpotifySecret}
							<input class="text" type="text" bind:value={spotifyClientSecret} placeholder={t('settings.apis.spotifyClientSecret')} autocomplete="off" />
						{:else}
							<input class="text" type="password" bind:value={spotifyClientSecret} placeholder={t('settings.apis.spotifyClientSecret')} autocomplete="off" />
						{/if}
						<button class="btn" type="button" onclick={() => showSpotifySecret = !showSpotifySecret}>{showSpotifySecret ? '🙈' : '👁'}</button>
					</div>
					<p class="cx-hint">{@html t('settings.apis.spotifyHint')}</p>
				</div>
			</div>
		</div>

		<!-- Steam (full width) -->
		<div class="glass cx-card cx-span2" style="--accent: var(--game);">
			<div class="cx-card-head">
				<div class="cx-ico">🎮</div>
				<div class="cx-htxt">
					<div class="cx-title">Steam</div>
					<div class="cx-sub">{t('settings.steam.subtitle')}</div>
				</div>
				<span class="cx-dot" class:ok={!!auth.user?.steam_id}>{auth.user?.steam_id ? t('settings.steam.connected') : t('settings.steam.notConnected')}</span>
			</div>
			<div class="cx-body">
				<div class="cx-field">
					<label for="cx-steam">{t('settings.steam.apiKeyLabel')}</label>
					<input id="cx-steam" class="text" type="password" bind:value={steamApiKey} placeholder={t('settings.steam.apiKeyPlaceholder')} autocomplete="off" />
					<p class="cx-hint">{@html t('settings.steam.apiKeyHint')}</p>
				</div>

				{#if auth.user?.steam_id}
					<div class="cx-steam-connect">
						<div class="settings-row" style="border:none; padding:0;">
							<span class="k">{t('settings.steam.steamId')}</span>
							<span class="v steam-id">{auth.user.steam_id}</span>
						</div>
						<div style="display:flex; gap:8px; flex-wrap:wrap;">
							<button class="btn cx-btn-steam" onclick={steamSync} disabled={steamSyncState === 'syncing'} style="flex:1; justify-content:center;">
								{steamSyncState === 'syncing' ? t('settings.steam.syncing') : t('settings.steam.syncButton')}
							</button>
							<button class="btn" onclick={steamDisconnect} style="opacity:0.6; font-size:12px;">{t('settings.steam.disconnect')}</button>
						</div>
						{#if steamSyncState === 'done' && steamSyncResult}
							<p class="cx-hint" style="color:var(--game);">{tc('settings.steam.synced', steamSyncResult.synced, { total: steamSyncResult.total_steam_games })}</p>
						{:else if steamSyncState === 'error'}
							<p class="cx-hint" style="color:var(--red, var(--danger));">{t('settings.steam.syncError')}</p>
						{/if}
					</div>
				{:else}
					<div class="cx-steam-connect">
						<p>{t('settings.steam.connectPrompt')}</p>
						<button class="btn cx-btn-steam" onclick={() => window.location.href = `/api/auth/steam/login?token=${auth.token}${steamApiKey ? '&steam_api_key=' + encodeURIComponent(steamApiKey) : ''}`}>
							{t('settings.steam.connectButton')}
						</button>
						<p class="cx-hint">{@html t('settings.steam.connectHint')}</p>
					</div>
				{/if}
			</div>
		</div>

	</div><!-- /cx-grid -->

	<!-- Save bar -->
	<div class="glass-strong cx-savebar">
		<button class="btn btn-primary" onclick={saveLocalSettings}>{t('settings.save')}</button>
		<button class="btn" onclick={resetLocalSettings}>{t('settings.resetReading')}</button>
		{#if saved}<span class="cx-saved">{t('settings.saved')}</span>{/if}
	</div>

	<!-- Sesión -->
	<div class="glass cx-card cx-session" style="--accent: var(--danger); margin-top:14px;">
		<div class="cx-card-head">
			<div class="cx-ico">🔐</div>
			<div class="cx-htxt">
				<div class="cx-title">{t('settings.session.title')}</div>
				<div class="cx-sub">{t('settings.session.connectedAs', { name: auth.user?.name ?? '' })}</div>
			</div>
			<button class="btn btn-danger" onclick={logout} style="padding:9px 18px;">{t('nav.logout')}</button>
		</div>
	</div>

	<!-- Mantenimiento -->
	<details class="glass cx-card cx-maint" style="margin-top:14px;">
		<summary>
			<span>🛠️</span><span>{t('settings.maintenance.title')}</span><span class="chev">›</span>
		</summary>
		<div class="cx-body" style="padding-top:0;">
			<p class="cx-hint" style="color:var(--text-muted); line-height:1.5;">
				{@html t('settings.maintenance.hint')}
			</p>
			<div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
				<button class="btn" onclick={() => runTmdbBackfill(false)} disabled={backfillState === 'running'}>
					{backfillState === 'running' ? t('settings.maintenance.updating') : t('settings.maintenance.updateButton')}
				</button>
				<button class="btn" onclick={() => runTmdbBackfill(true)} disabled={backfillState === 'running'} style="opacity:0.6; font-size:11px;">{t('settings.maintenance.forceAll')}</button>
			</div>
			{#if backfillState === 'done'}
				<p class="cx-hint" style="color:var(--game);">{t('settings.maintenance.backfillStarted')}</p>
			{:else if backfillState === 'error'}
				<p class="cx-hint" style="color:var(--red, var(--danger));">{t('settings.maintenance.backfillError')}</p>
			{/if}
		</div>
	</details>

	<div class="cx-footer">
		<a href="https://ko-fi.com/Z8Z81OW7UV" target="_blank" rel="noopener noreferrer" class="btn" style="font-size:12px;">{t('settings.kofi')}</a>
	</div>
{/if}

<style>
	/* ════════ AJUSTES — REDISEÑO ════════ */

	.cx-mtitle { font-size: 26px; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 16px; }
	.cx-toptag { font-size: 12px; color: var(--text-muted); font-weight: 500; }

	/* ── Identity header ── */
	.cx-head {
		position: relative;
		display: flex; align-items: center; gap: 18px;
		padding: 22px;
		margin-bottom: 18px;
		border-radius: var(--radius);
		overflow: hidden;
	}
	.cx-head::after {
		content: ''; position: absolute; inset: 0; pointer-events: none; z-index: 0;
		background:
			radial-gradient(120% 140% at 0% 0%, oklch(0.78 0.16 300 / 0.30), transparent 55%),
			radial-gradient(120% 140% at 100% 100%, oklch(0.74 0.16 210 / 0.22), transparent 55%);
	}
	.cx-head > :global(*) { position: relative; z-index: 1; }
	.cx-av {
		width: 64px; height: 64px; border-radius: 50%; flex-shrink: 0;
		display: grid; place-items: center;
		font-size: 26px; font-weight: 800; color: #fff;
		background: linear-gradient(135deg, oklch(0.80 0.16 290), oklch(0.62 0.20 250));
		box-shadow: 0 0 0 3px oklch(0.80 0.12 290 / 0.25), 0 8px 24px oklch(0.55 0.18 290 / 0.45);
	}
	.cx-id { flex: 1; min-width: 0; }
	.cx-kicker { font-size: 10px; font-weight: 700; letter-spacing: 0.3em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 6px; }
	.cx-name { font-size: 24px; font-weight: 800; letter-spacing: -0.02em; line-height: 1; }
	.cx-email { font-size: 13px; color: var(--text-muted); margin-top: 5px; }
	.cx-brand { display: none; text-align: right; flex-shrink: 0; }
	.cx-brand .mk { font-size: 22px; line-height: 1; }
	.cx-brand .tg { font-size: 11px; font-style: italic; color: var(--text-dim); letter-spacing: 0.08em; margin-top: 4px; }
	@media (min-width: 720px) { .cx-brand { display: block; } }

	/* ── Bento grid ── */
	.cx-grid { display: flex; flex-direction: column; gap: 14px; }
	@media (min-width: 1024px) {
		.cx-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
		.cx-span2 { grid-column: 1 / -1; }
	}

	/* ── Section card ── */
	.cx-card { --accent: var(--primary); padding: 0; border-radius: var(--radius); overflow: hidden; }
	.cx-card-head {
		display: flex; align-items: center; gap: 12px;
		padding: 16px 18px 14px;
		border-bottom: 1px solid var(--glass-border);
		position: relative;
	}
	.cx-card-head::before {
		content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
		background: var(--accent); box-shadow: 0 0 12px var(--accent);
	}
	.cx-ico {
		width: 36px; height: 36px; border-radius: 11px; flex-shrink: 0;
		display: grid; place-items: center; font-size: 18px;
		background: color-mix(in oklab, var(--accent) 18%, transparent);
		border: 1px solid color-mix(in oklab, var(--accent) 35%, transparent);
	}
	.cx-htxt { flex: 1; min-width: 0; }
	.cx-title { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
	.cx-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
	.cx-body { padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 16px; }
	.cx-label { font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 9px; display: block; }
	.cx-hint { font-size: 11px; color: var(--text-dim); line-height: 1.5; }
	.cx-hint strong { color: var(--text-muted); }
	.cx-salary-result { display:flex; align-items:baseline; gap:8px; background:oklch(0.82 0.18 75 / 0.1); border:1px solid oklch(0.82 0.18 75 / 0.25); border-radius:var(--radius-xs); padding:10px 14px; }
	.cx-salary-rate { font-size:18px; font-weight:700; color:oklch(0.82 0.18 75); }
	.cx-salary-label { font-size:11px; color:var(--text-dim); }

	/* ── Theme tiles ── */
	.cx-theme-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
	.cx-theme {
		all: unset; cursor: pointer; border-radius: 14px; overflow: hidden;
		border: 1px solid var(--glass-border); position: relative;
		transition: border-color .15s, box-shadow .15s;
	}
	.cx-theme.on { border-color: var(--glass-border-bright); box-shadow: 0 0 0 2px var(--primary); }
	.cx-theme-prev { height: 58px; display: flex; align-items: center; gap: 6px; padding: 12px; }
	.cx-theme-prev .swatch { width: 22px; height: 22px; border-radius: 6px; }
	.cx-theme-prev .lines { flex: 1; display: flex; flex-direction: column; gap: 5px; }
	.cx-theme-prev .lines i { height: 5px; border-radius: 3px; display: block; }
	.cx-theme.dark  .cx-theme-prev { background: linear-gradient(135deg, #14121f, #1d1830); }
	.cx-theme.dark  .swatch { background: linear-gradient(135deg, oklch(0.78 0.16 290), oklch(0.62 0.20 250)); }
	.cx-theme.dark  .lines i { background: rgba(255,255,255,0.22); }
	.cx-theme.dark  .lines i:first-child { background: rgba(255,255,255,0.45); width: 70%; }
	.cx-theme.light .cx-theme-prev { background: linear-gradient(135deg, #efe9ff, #fdfbff); }
	.cx-theme.light .swatch { background: linear-gradient(135deg, oklch(0.72 0.16 290), oklch(0.6 0.2 250)); }
	.cx-theme.light .lines i { background: rgba(40,20,70,0.20); }
	.cx-theme.light .lines i:first-child { background: rgba(40,20,70,0.42); width: 70%; }
	.cx-theme-tag {
		display: flex; align-items: center; justify-content: space-between;
		padding: 8px 12px; font-size: 12px; font-weight: 600;
		background: var(--glass-bg-weak);
	}
	.cx-theme-tag .chk { opacity: 0; color: var(--primary); font-weight: 800; }
	.cx-theme.on .cx-theme-tag .chk { opacity: 1; }

	/* ── Wallpaper swatches ── */
	.cx-wp-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
	.cx-wp { all: unset; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 7px; transition: transform .12s; }
	.cx-wp:hover { transform: translateY(-2px); }
	.cx-wp-sw {
		width: 100%; aspect-ratio: 1; border-radius: 13px; overflow: hidden;
		display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
		border: 1px solid var(--glass-border); position: relative; box-shadow: var(--glass-inner);
	}
	.cx-wp-sw i { display: block; }
	.cx-wp.on .cx-wp-sw { box-shadow: 0 0 0 2px var(--primary), 0 6px 18px rgba(0,0,0,0.4); }
	.cx-wp-sw .chk {
		position: absolute; inset: 0; display: grid; place-items: center;
		font-size: 18px; color: #fff; opacity: 0;
		background: rgba(0,0,0,0.35); text-shadow: 0 1px 4px rgba(0,0,0,0.6);
	}
	.cx-wp.on .cx-wp-sw .chk { opacity: 1; }
	.cx-wp span { font-size: 11px; font-weight: 600; color: var(--text-muted); }
	.cx-wp.on span { color: var(--text); }

	/* ── Blur control + live demo ── */
	.cx-blur { display: grid; grid-template-columns: 1fr auto; gap: 14px; align-items: center; }
	.cx-blur-demo {
		width: 74px; height: 74px; border-radius: 16px; flex-shrink: 0; position: relative; overflow: hidden;
		background: conic-gradient(from 45deg, oklch(0.78 0.2 300), oklch(0.78 0.2 200), oklch(0.8 0.18 140), oklch(0.78 0.2 340), oklch(0.78 0.2 300));
	}
	.cx-blur-demo .panel {
		position: absolute; inset: 14px; border-radius: 10px;
		background: var(--glass-bg); border: 1px solid var(--glass-border-bright);
		-webkit-backdrop-filter: blur(var(--blur)); backdrop-filter: blur(var(--blur));
		display: grid; place-items: center; font-size: 10px; font-weight: 700; color: var(--text);
	}
	.cx-range { width: 100%; accent-color: var(--primary); }
	.cx-blur-val { font-variant-numeric: tabular-nums; color: var(--text); font-weight: 700; }

	/* ── Fields ── */
	.cx-field { display: flex; flex-direction: column; gap: 7px; }
	.cx-field > label, .cx-field > span.cx-label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
	.cx-two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
	.cx-two :global(.text) { width: 100%; }
	.cx-input-unit { position: relative; }
	.cx-input-unit .u { position: absolute; right: 14px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--text-dim); pointer-events: none; font-weight: 600; }

	/* ── Reading speed test ── */
	.cx-test-text {
		background: var(--glass-bg-weak);
		border: 1px solid var(--glass-border);
		border-radius: 10px;
		padding: 12px 14px;
		font-size: 13px;
		line-height: 1.7;
		color: var(--text);
		user-select: none;
	}
	.cx-test-result {
		display: flex;
		align-items: baseline;
		gap: 6px;
		flex-wrap: wrap;
		background: color-mix(in oklab, var(--book) 10%, transparent);
		border: 1px solid color-mix(in oklab, var(--book) 25%, transparent);
		border-radius: 10px;
		padding: 12px 14px;
	}
	.cx-test-wpm { font-size: 32px; font-weight: 800; color: var(--book); }
	.cx-test-unit { font-size: 14px; font-weight: 600; color: var(--text-muted); }
	.cx-test-meta { margin-left: auto; font-size: 11px; color: var(--text-dim); }

	/* ── API rows ── */
	.cx-api { display: flex; flex-direction: column; gap: 7px; }
	.cx-api :global(.text) { width: 100%; }
	.cx-api-top { display: flex; align-items: center; gap: 9px; }
	.cx-api-glyph {
		width: 26px; height: 26px; border-radius: 8px; flex-shrink: 0;
		display: grid; place-items: center; font-size: 13px; font-weight: 800;
		background: color-mix(in oklab, var(--g, var(--primary)) 18%, transparent);
		color: var(--g, var(--primary));
		border: 1px solid color-mix(in oklab, var(--g, var(--primary)) 35%, transparent);
	}
	.cx-api-name { font-size: 13px; font-weight: 700; flex: 1; }
	.cx-dot { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: var(--text-dim); }
	.cx-dot::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--text-dim); }
	.cx-dot.ok { color: var(--game); }
	.cx-dot.ok::before { background: var(--game); box-shadow: 0 0 8px var(--game); }
	.cx-pwrow { display: flex; gap: 8px; }
	.cx-pwrow :global(.text) { flex: 1; }

	/* ── Steam connect ── */
	.cx-steam-connect {
		display: flex; flex-direction: column; gap: 12px;
		padding: 16px; border-radius: 14px;
		background: color-mix(in oklab, var(--game) 8%, transparent);
		border: 1px solid color-mix(in oklab, var(--game) 22%, transparent);
	}
	.cx-steam-connect p { font-size: 13px; color: var(--text-muted); line-height: 1.5; }
	.cx-btn-steam {
		background: linear-gradient(180deg, oklch(0.5 0.07 230), oklch(0.36 0.06 235));
		color: #fff; border: none; font-weight: 700;
		box-shadow: 0 4px 16px oklch(0.4 0.08 235 / 0.5), var(--glass-inner);
	}
	.cx-btn-steam:hover { filter: brightness(1.1); }
	.steam-id { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }

	/* ── Maintenance ── */
	.cx-maint summary { list-style: none; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: var(--text-muted); padding: 16px 18px; }
	.cx-maint summary::-webkit-details-marker { display: none; }
	.cx-maint summary .chev { margin-left: auto; transition: transform .2s; color: var(--text-dim); }
	.cx-maint[open] summary .chev { transform: rotate(90deg); }

	/* ── Save bar ── */
	.cx-savebar { display: flex; gap: 10px; align-items: center; padding: 12px 14px; margin-top: 16px; border-radius: 18px; }
	@media (min-width: 1024px) { .cx-savebar { position: sticky; bottom: 14px; z-index: 5; } }
	.cx-savebar :global(.btn) { flex: 1; justify-content:center; }
	.cx-saved { color: var(--game); font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }

	.cx-footer { text-align: center; margin-top: 18px; padding-bottom: 6px; }

</style>
