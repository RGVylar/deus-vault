<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl, isLookupCandidate } from '$lib/utils';
	import { quickAdd } from '$lib/stores/quickadd.svelte';
	import type { Content, VaultStats, ContentType, PaginatedContents } from '$lib/types';

	const LIMIT = 20;

	// Type accent colors matching CSS vars
	const TYPE_COLOR: Record<string, string> = {
		youtube: 'var(--youtube)',
		movie:   'var(--movie)',
		series:  'var(--series)',
		book:    'var(--book)',
		game:    'var(--game)',
		music:   'var(--music)',
	};

	// Landscape layout: video + game content has wide thumbnails → banner at top
	// Books and music have portrait/square covers → side column
	function isLandscape(type: ContentType): boolean {
		return type === 'youtube' || type === 'movie' || type === 'series' || type === 'game';
	}

	// For portrait cards (books, music only)
	function thumbClass(_type: ContentType): string {
		return 'thumb';
	}

	let stats: VaultStats | null = $state(null);
	let contents: Content[] = $state([]);
	let total = $state(0);
	let offset = $state(0);
	let filter: ContentType | 'all' = $state('all');
	let sortOrder = $state('recent');
	let searchQuery = $state('');
	let activeCollection = $state<string | null>(null);
	let collections: string[] = $state([]);
	let showAdd = $state(false);
	let loading = $state(true);
	let loadingMore = $state(false);

	// Progress editing
	let editingProgressId = $state<number | null>(null);
	let progressValue = $state(0);

	// Delete confirmation
	let deletingId = $state<number | null>(null);

	// Edit modal
	let editingItem = $state<Content | null>(null);
	let editTitle = $state('');
	let editUrl = $state('');
	let editAuthor = $state('');
	let editThumbnail = $state('');
	let editDuration = $state(0);
	let editPageCount = $state<number | null>(null);
	let editEpisodeCount = $state<number | null>(null);
	let editSeasons = $state<number | null>(null);
	let editNotes = $state('');
	let editCollection = $state('');
	let editPinned = $state(false);
	let editError = $state('');

	// Settings
	let showSettings = $state(false);
	let readingWpm = $state(200);
	let readingWordsPerPage = $state(300);

	// Add form
	let addTitle = $state('');
	let addType: ContentType = $state('youtube');
	let addUrl = $state('');
	let addDuration = $state(0);
	let addPageCount = $state(0);
	let addWordsPerPage = $state(300); // reset to readingWordsPerPage in resetForm()
	let addBookFormat: 'book' | 'manga' = $state('book');
	let addEpisodeCount = $state(0);
	let addSeasons = $state(0);
	let addAuthor = $state('');
	let addNotes = $state('');
	let addThumbnail = $state('');
	let addChannelThumbnail = $state('');
	let addSourceId = $state('');
	let addCollection = $state('');
	let addPinned = $state(false);
	let addAlreadyConsumed = $state(false);
	let addError = $state('');
	let lookupLoading = $state(false);
	let lastLookupUrl = $state('');
	let refreshingId = $state<number | null>(null);
	let autoLookupTimer: ReturnType<typeof setTimeout> | null = null;
	let searchTimer: ReturnType<typeof setTimeout> | null = null;

	// Duplicate detection + new lookup fields
	let duplicateItem = $state<Content | null>(null);
	let duplicateChecked = $state(false);
	let addNextEpisodeDate = $state<string | null>(null);
	let addWatchProviders = $state<Array<{provider_name: string; logo_path: string}>>([]);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		load();
		try {
			const stored = localStorage.getItem('deus_vault_reading_wpm');
			if (stored) readingWpm = Number(stored) || readingWpm;
			const storedPages = localStorage.getItem('deus_vault_words_per_page');
			if (storedPages) readingWordsPerPage = Number(storedPages) || readingWordsPerPage;
		} catch (e) {}

		const handler = (ev: Event) => {
			try {
				const d = (ev as CustomEvent).detail || {};
				if (d.readingWpm) readingWpm = Number(d.readingWpm) || readingWpm;
				if (d.readingWordsPerPage) {
					readingWordsPerPage = Number(d.readingWordsPerPage) || readingWordsPerPage;
					addWordsPerPage = readingWordsPerPage;
				}
			} catch (e) {}
		};
		window.addEventListener('deus_vault_settings_changed', handler as EventListener);
		return () => window.removeEventListener('deus_vault_settings_changed', handler as EventListener);
	});

	// React to URLs pasted from anywhere in the app (set by layout)
	$effect(() => {
		const url = quickAdd.pendingUrl;
		if (!url) return;
		quickAdd.pendingUrl = '';
		if (showAdd) return;
		resetForm();
		addUrl = url;
		showAdd = true;
	});

	function buildUrl(consumed: boolean, type: ContentType | 'all', off: number, search: string, sort = 'recent', col: string | null = null) {
		let url = `/contents?consumed=${consumed}&limit=${LIMIT}&offset=${off}&sort=${sort}`;
		if (type !== 'all') url += `&content_type=${type}`;
		if (search.trim()) url += `&search=${encodeURIComponent(search.trim())}`;
		if (col) url += `&collection=${encodeURIComponent(col)}`;
		return url;
	}

	async function loadCollections() {
		try {
			collections = await api.get<string[]>('/contents/collections');
		} catch { collections = []; }
	}

	async function load() {
		loading = true;
		offset = 0;
		try {
			const [s, p] = await Promise.all([
				api.get<VaultStats>('/contents/stats'),
				api.get<PaginatedContents>(buildUrl(false, filter, 0, searchQuery, sortOrder, activeCollection))
			]);
			stats = s;
			contents = p.items;
			total = p.total;
			await loadCollections();
		} finally { loading = false; }
	}

	async function loadMore() {
		loadingMore = true;
		const newOffset = offset + LIMIT;
		try {
			const p = await api.get<PaginatedContents>(buildUrl(false, filter, newOffset, searchQuery, sortOrder, activeCollection));
			contents = [...contents, ...p.items];
			total = p.total;
			offset = newOffset;
		} finally { loadingMore = false; }
	}

	// React to filter, sort, or collection changes
	let controlsMounted = false;
	$effect(() => {
		const _filter = filter;
		const _sort = sortOrder;
		const _col = activeCollection;
		if (!controlsMounted) { controlsMounted = true; return; }
		if (!auth.isLoggedIn) return;
		offset = 0;
		api.get<PaginatedContents>(buildUrl(false, _filter, 0, searchQuery, _sort, _col)).then(p => {
			contents = p.items;
			total = p.total;
		});
	});

	// Debounced search
	$effect(() => {
		const q = searchQuery;
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			if (!auth.isLoggedIn) return;
			offset = 0;
			api.get<PaginatedContents>(buildUrl(false, filter, 0, q, sortOrder, activeCollection)).then(p => {
				contents = p.items;
				total = p.total;
			});
		}, 300);
		return () => { if (searchTimer) clearTimeout(searchTimer); };
	});

	// --- Lookup ---
$effect(() => {
		const url = addUrl.trim();
		if (!showAdd || !url || !isLookupCandidate(url) || lookupLoading || url === lastLookupUrl) return;
		if (autoLookupTimer) clearTimeout(autoLookupTimer);
		autoLookupTimer = setTimeout(() => { void lookupUrl(url); }, 350);
		return () => { if (autoLookupTimer) { clearTimeout(autoLookupTimer); autoLookupTimer = null; } };
	});

	async function lookupUrl(overrideUrl?: string) {
		const targetUrl = (overrideUrl ?? addUrl).trim();
		if (!targetUrl) return;
		addError = '';
		lookupLoading = true;
		try {
			const params = new URLSearchParams({ url: targetUrl });
			try {
				const tmdbKey = localStorage.getItem('deus_vault_tmdb_api_key');
				const spotifyId = localStorage.getItem('deus_vault_spotify_client_id');
				const spotifySecret = localStorage.getItem('deus_vault_spotify_client_secret');
				if (tmdbKey) params.set('tmdb_api_key', tmdbKey);
				if (spotifyId) params.set('spotify_client_id', spotifyId);
				if (spotifySecret) params.set('spotify_client_secret', spotifySecret);
			} catch (e) {}
			const data = await api.get<any>(`/lookup/auto?${params.toString()}`);
			addTitle = data.title || addTitle;
			addAuthor = data.author || addAuthor;
			addThumbnail = data.thumbnail || '';
			addChannelThumbnail = data.channel_thumbnail || '';
			addSourceId = data.source_id || '';
			const suggestedType = data.suggested_content_type;
			if (suggestedType) addType = suggestedType;
			else if (targetUrl.includes('youtube.com') || targetUrl.includes('youtu.be')) addType = 'youtube';
			else if (targetUrl.includes('store.steampowered.com')) addType = 'game';
			if (addType === 'book') {
				if (data.page_count && Number(data.page_count) > 0) {
					addPageCount = Number(data.page_count);
					if (data.words_per_page) addWordsPerPage = Number(data.words_per_page);
					addDuration = Math.ceil(Number(addPageCount) * Number(addWordsPerPage) / Math.max(1, Number(readingWpm)));
				} else if (data.duration_minutes) {
					addDuration = data.duration_minutes;
					if (data.page_count) addPageCount = Number(data.page_count);
					if (data.words_per_page) addWordsPerPage = Number(data.words_per_page);
				}
			} else {
				if (data.duration_minutes) addDuration = data.duration_minutes;
			}
			if (addType === 'series') {
				if (data.episode_count) addEpisodeCount = Number(data.episode_count);
				if (data.seasons) addSeasons = Number(data.seasons);
			}
			lastLookupUrl = targetUrl;

			// Parse new fields
			addNextEpisodeDate = (addType === 'series' && data.next_episode_date) ? data.next_episode_date : null;
			addWatchProviders = data.watch_providers ?? [];

			// Duplicate check
			duplicateItem = null;
			duplicateChecked = false;
			const checkId = addSourceId || '';
			const checkUrl = targetUrl;
			if (checkId || checkUrl) {
				try {
					const p = new URLSearchParams();
					if (checkId) p.set('source_id', checkId);
					else p.set('url', checkUrl);
					duplicateItem = await api.get<Content | null>(`/contents/check-duplicate?${p.toString()}`);
				} catch { /* ignore */ }
				duplicateChecked = true;
			}
		} catch (e: unknown) {
			addError = e instanceof Error ? e.message : 'Lookup failed';
		} finally { lookupLoading = false; }
	}

	async function submitAdd() {
		addError = '';
		// Block if pending duplicate
		if (duplicateItem && !duplicateItem.consumed && !duplicateItem.abandoned) {
			addError = 'Este ítem ya está en tu bóveda como pendiente.';
			return;
		}
		// If already consumed, increment times_consumed on the existing item instead of creating a new one
		if (duplicateItem && duplicateItem.consumed) {
			await api.post(`/contents/${duplicateItem.id}/consume`);
			showAdd = false;
			resetForm();
			load();
			return;
		}
		try {
			const created = await api.post<{ id: number }>('/contents', {
				title: addTitle, content_type: addType, url: addUrl || null,
				thumbnail: addThumbnail || null, duration_minutes: addDuration,
				page_count: addPageCount && Number(addPageCount) > 0 ? Number(addPageCount) : null,
				words_per_page: addWordsPerPage && Number(addWordsPerPage) > 0 ? Number(addWordsPerPage) : null,
				episode_count: addType === 'series' && addEpisodeCount > 0 ? addEpisodeCount : null,
				seasons: addType === 'series' && addSeasons > 0 ? addSeasons : null,
				source_id: addSourceId || null, author: addAuthor || null, notes: addNotes || null,
				collection: addCollection.trim() || null, pinned: addPinned,
				channel_thumbnail: addChannelThumbnail || null,
				next_episode_date: addNextEpisodeDate || null,
			});
			if (addAlreadyConsumed && created?.id) {
				await api.post(`/contents/${created.id}/consume`);
			}
			showAdd = false;
			resetForm();
			load();
		} catch (e: unknown) { addError = e instanceof Error ? e.message : 'Error'; }
	}

	function saveSettings() {
		try {
			localStorage.setItem('deus_vault_reading_wpm', String(readingWpm));
			localStorage.setItem('deus_vault_words_per_page', String(readingWordsPerPage));
		} catch (e) {}
		showSettings = false;
		try { window.dispatchEvent(new CustomEvent('deus_vault_settings_changed', { detail: { readingWpm, readingWordsPerPage } })); } catch (e) {}
	}

	function resetForm() {
		addTitle = ''; addUrl = ''; addDuration = 0; addAuthor = '';
		addNotes = ''; addThumbnail = ''; addChannelThumbnail = ''; addSourceId = ''; addType = 'youtube';
		addPageCount = 0; addWordsPerPage = readingWordsPerPage; addBookFormat = 'book';
		addEpisodeCount = 0; addSeasons = 0; lastLookupUrl = '';
		addCollection = ''; addPinned = false; addAlreadyConsumed = false;
		duplicateItem = null; duplicateChecked = false;
		addNextEpisodeDate = null; addWatchProviders = [];
	}

	async function consume(id: number) { await api.post(`/contents/${id}/consume`); load(); }
	async function abandon(id: number) { await api.post(`/contents/${id}/abandon`); load(); }
	async function remove(id: number) {
		deletingId = null;
		await api.del(`/contents/${id}`);
		load();
	}

	async function togglePin(c: Content) {
		const newPinned = !c.pinned;
		contents = contents.map(x => x.id === c.id ? { ...x, pinned: newPinned } : x);
		await api.patch(`/contents/${c.id}`, { pinned: newPinned });
		api.get<VaultStats>('/contents/stats').then(s => { stats = s; });
	}

	async function refresh(c: Content) {
		if (!c.url || refreshingId !== null) return;
		refreshingId = c.id;
		try {
			const params = new URLSearchParams({ url: c.url });
			try {
				const tmdbKey = localStorage.getItem('deus_vault_tmdb_api_key');
				const spotifyId = localStorage.getItem('deus_vault_spotify_client_id');
				const spotifySecret = localStorage.getItem('deus_vault_spotify_client_secret');
				if (tmdbKey) params.set('tmdb_api_key', tmdbKey);
				if (spotifyId) params.set('spotify_client_id', spotifyId);
				if (spotifySecret) params.set('spotify_client_secret', spotifySecret);
			} catch (e) {}
			const data = await api.get<any>(`/lookup/auto?${params.toString()}`);
			const patch: Record<string, unknown> = {};
			if (data.title) patch.title = data.title;
			if (data.author) patch.author = data.author;
			if (data.thumbnail) patch.thumbnail = data.thumbnail;
			if (data.duration_minutes) patch.duration_minutes = data.duration_minutes;
			if (data.episode_count != null) patch.episode_count = data.episode_count;
			if (data.seasons != null) patch.seasons = data.seasons;
			if (data.page_count && Number(data.page_count) > 0) patch.page_count = data.page_count;
			if (data.next_episode_date !== undefined) patch.next_episode_date = data.next_episode_date ?? null;
			await api.patch(`/contents/${c.id}`, patch);
			load();
		} catch (e) { /* silent */ } finally { refreshingId = null; }
	}

	// --- Edit modal ---
	function startEdit(c: Content) {
		editingItem = c;
		editTitle = c.title;
		editUrl = c.url ?? '';
		editAuthor = c.author ?? '';
		editThumbnail = c.thumbnail ?? '';
		editDuration = c.duration_minutes;
		editPageCount = c.page_count ?? null;
		editEpisodeCount = c.episode_count ?? null;
		editSeasons = c.seasons ?? null;
		editNotes = c.notes ?? '';
		editCollection = c.collection ?? '';
		editPinned = c.pinned;
		editError = '';
	}

	async function saveEdit() {
		if (!editingItem) return;
		editError = '';
		try {
			const patch: Record<string, unknown> = {
				title: editTitle.trim() || editingItem.title,
				url: editUrl.trim() || null,
				author: editAuthor.trim() || null,
				thumbnail: editThumbnail.trim() || null,
				duration_minutes: Math.max(0, Number(editDuration) || 0),
				notes: editNotes.trim() || null,
				collection: editCollection.trim() || null,
				pinned: editPinned,
			};
			if (editingItem.content_type === 'book') {
				patch.page_count = editPageCount ? Number(editPageCount) : null;
			}
			if (editingItem.content_type === 'series') {
				patch.episode_count = editEpisodeCount ? Number(editEpisodeCount) : null;
				patch.seasons = editSeasons ? Number(editSeasons) : null;
			}
			const updated = await api.patch<Content>(`/contents/${editingItem.id}`, patch);
			contents = contents.map(x => x.id === editingItem!.id ? updated : x);
			editingItem = null;
			await loadCollections();
			api.get<VaultStats>('/contents/stats').then(s => { stats = s; });
		} catch (e: unknown) {
			editError = e instanceof Error ? e.message : 'Error al guardar';
		}
	}

	// --- Progress helpers ---
	function remainingMinutes(c: Content): number {
		const progress = c.progress ?? 0;
		if (c.content_type === 'series') {
			const totalEps = c.episode_count ?? 0;
			if (totalEps > 0) return Math.max(0, (totalEps - Math.min(progress, totalEps)) * c.duration_minutes);
			return c.duration_minutes;
		}
		const total = c.duration_minutes;
		if (progress <= 0) return total;
		if (c.content_type === 'book' && c.page_count && c.page_count > 0)
			return Math.max(0, Math.round(total * Math.max(0, c.page_count - progress) / c.page_count));
		if (c.content_type === 'game')
			return Math.max(0, Math.round(total * Math.max(0, 100 - progress) / 100));
		return Math.max(0, total - progress); // movie, youtube, music
	}

	function progressPercent(c: Content): number {
		const p = c.progress ?? 0;
		if (p <= 0) return 0;
		if (c.content_type === 'book' && c.page_count && c.page_count > 0)
			return Math.min(100, (p / c.page_count) * 100);
		if (c.content_type === 'game') return Math.min(100, p);
		if (c.content_type === 'series' && c.episode_count && c.episode_count > 0)
			return Math.min(100, (p / c.episode_count) * 100);
		if (c.duration_minutes > 0) return Math.min(100, (p / c.duration_minutes) * 100);
		return 0;
	}

	function progressLabel(c: Content): string {
		const p = c.progress ?? 0;
		if (p <= 0) return '';
		if (c.content_type === 'book') return `Pág. ${p}${c.page_count ? ' / ' + c.page_count : ''}`;
		if (c.content_type === 'game') return `${p}%`;
		if (c.content_type === 'series') return `Ep. ${p}${c.episode_count ? ' / ' + c.episode_count : ''}`;
		return `${p} min`;
	}

	function progressInputLabel(c: Content): string {
		if (c.content_type === 'book') return `Página actual${c.page_count ? ' (1–' + c.page_count + ')' : ''}`;
		if (c.content_type === 'game') return '% completado (0–100)';
		if (c.content_type === 'series') return `Episodio${c.episode_count ? ' (1–' + c.episode_count + ')' : ''}`;
		return `Minuto actual${c.duration_minutes ? ' (0–' + c.duration_minutes + ')' : ''}`;
	}

	function startEditProgress(c: Content) {
		editingProgressId = c.id;
		progressValue = c.progress ?? 0;
	}

	async function saveProgress(c: Content) {
		editingProgressId = null;
		const val = Math.max(0, Math.floor(progressValue));
		contents = contents.map(x => x.id === c.id ? { ...x, progress: val } : x);
		await api.patch(`/contents/${c.id}`, { progress: val });
		// Refresh stats silently (debt changed)
		api.get<VaultStats>('/contents/stats').then(s => { stats = s; });
	}

	// Stats pill total for proportional bars
	const totalByTypeMins = $derived(
		stats ? Object.values(stats.by_type).reduce((a, b) => a + b, 0) : 0
	);

	function formatHeroTime(minutes: number): string {
		if (minutes < 60) return `${minutes} min`;
		return `${Math.floor(minutes / 60)} h`;
	}
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">Redirigiendo…</p>
{:else}

	<!-- ── Desktop topbar (search + sort integrated) ── -->
	<div class="desk-topbar desk-only">
		<h1 class="desk-title">Bóveda</h1>
		<div class="desk-search">
			<span class="ico">🔍</span>
			<input type="search" bind:value={searchQuery} placeholder="Buscar en la bóveda…" />
		</div>
		<select class="sort" bind:value={sortOrder} style="max-width:150px;">
			<option value="recent">📅 Recientes</option>
			<option value="duration_asc">⏱ Duración ↑</option>
			<option value="duration_desc">⏱ Duración ↓</option>
			<option value="title_asc">🔤 Título A–Z</option>
		</select>
	</div>

	{#if stats}
		<!-- Hero + quick stats (grid on desktop, stacked on mobile) -->
		<div class="desk-hero-grid">
			<div class="hero">
				<div class="kicker">DEUDA PENDIENTE</div>
				<div class="number">{formatHeroTime(stats.total_pending_minutes)}</div>
				<div class="unit">{formatDuration(stats.total_pending_minutes)} totales por consumir</div>
				<div class="sub">La bóveda no espera</div>
			</div>

			<!-- Distribution card: desktop only -->
			{#if Object.keys(stats.by_type).length > 0}
				<div class="desk-quick desk-only">
					<h3>Distribución</h3>
					{#each Object.entries(stats.by_type).sort((a,b) => b[1]-a[1]) as [type, mins]}
						{@const pct = totalByTypeMins > 0 ? (mins / totalByTypeMins) * 100 : 0}
						<div class="dq-row">
							<span class="lbl"><span>{TYPE_ICONS[type] || '📄'}</span>{TYPE_LABELS[type] || type}</span>
							<div class="dq-bar"><div class="dq-bar-fill" style="width:{pct}%; --bar-color:{TYPE_COLOR[type] ?? 'var(--primary)'}"></div></div>
							<span class="val">{formatDuration(mins)}</span>
						</div>
					{/each}
					<div class="dq-footer">
						<span style="font-size:12px; color:var(--text-muted);">{stats.pending_count} pendientes · {stats.consumed_count} consumidos</span>
						<button class="btn btn-primary" onclick={() => showAdd = true} style="padding:6px 14px; font-size:12px;">+ Añadir</button>
					</div>
				</div>
			{/if}
		</div>

		<!-- Mobile-only pill stats -->
		<div class="mobile-only">
			<div class="pill-row">
				<div class="pill">
					<span>📦</span> <span class="val">{stats.pending_count}</span> <span class="lbl">pendientes</span>
				</div>
				<div class="pill">
					<span>✅</span> <span class="val">{stats.consumed_count}</span> <span class="lbl">consumidos</span>
				</div>
			</div>
			{#if Object.keys(stats.by_type).length > 0}
				<div class="pill-row">
					{#each Object.entries(stats.by_type) as [type, mins]}
						{@const pct = totalByTypeMins > 0 ? (mins / totalByTypeMins) * 100 : 0}
						<div class="pill pill-typed" style="--pill-color:{TYPE_COLOR[type] ?? 'var(--primary)'}">
							<span>{TYPE_ICONS[type] || '📄'}</span>
							<span class="val">{formatDuration(mins)}</span>
							{TYPE_LABELS[type] || type}
							<span class="pill-bar" style="width:{pct}%"></span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Section header + filter tabs -->
	<div class="desk-section desk-only">
		<h2>Pendiente</h2>
		<span class="more">{total} ítems</span>
	</div>
	<div class="tabs desk-tabs">
		<button class="tab" class:active={filter === 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class="tab" class:active={filter === 'youtube'} onclick={() => filter = 'youtube'}>▶️ YouTube</button>
		<button class="tab" class:active={filter === 'movie'} onclick={() => filter = 'movie'}>🎬 Películas</button>
		<button class="tab" class:active={filter === 'series'} onclick={() => filter = 'series'}>📺 Series</button>
		<button class="tab" class:active={filter === 'music'} onclick={() => filter = 'music'}>🎵 Música</button>
		<button class="tab" class:active={filter === 'book'} onclick={() => filter = 'book'}>📖 Libros</button>
		<button class="tab" class:active={filter === 'game'} onclick={() => filter = 'game'}>🎮 Juegos</button>
	</div>

	<!-- Search + sort (mobile only — desktop has it in topbar) -->
	<div class="search-row mobile-only">
		<div class="search">
			<span class="ico">🔍</span>
			<input
				type="search"
				bind:value={searchQuery}
				placeholder="Buscar…"
			/>
		</div>
		<select class="sort" bind:value={sortOrder}>
			<option value="recent">📅 Recientes</option>
			<option value="duration_asc">⏱ Duración ↑</option>
			<option value="duration_desc">⏱ Duración ↓</option>
			<option value="title_asc">🔤 Título A–Z</option>
		</select>
	</div>

	<!-- Collection filter chips -->
	{#if collections.length > 0}
		<div class="tabs" style="padding-top:0;">
			<button
				class="tab"
				class:active={activeCollection === null}
				onclick={() => activeCollection = null}
			>Todas</button>
			{#each collections as col}
				<button
					class="tab"
					class:active={activeCollection === col}
					onclick={() => activeCollection = activeCollection === col ? null : col}
				>📁 {col}</button>
			{/each}
		</div>
	{/if}

	<!-- Content list -->
	{#if loading}
		<p class="muted center">Cargando…</p>
	{:else if contents.length === 0}
		<div class="empty">
			<span class="icon">🏛️</span>
			<p>{searchQuery ? 'Sin resultados para "' + searchQuery + '"' : 'La bóveda está vacía. ¡Añade contenido!'}</p>
		</div>
	{:else}
		<div class="content-grid">
			{#each contents as c (c.id)}
				{@const link = buildConsumeUrl(c)}
				{@const pct = progressPercent(c)}
				{@const hasProgress = (c.progress ?? 0) > 0}
				{@const remaining = remainingMinutes(c)}
				{@const landscape = isLandscape(c.content_type)}
				<div
					class="c-card"
					class:landscape
					class:portrait={!landscape}
					style="--card-accent:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}; --accent:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}"
				>
					{#if landscape}
						<div class="thumb-land">
							{#if c.thumbnail}
								<img src={c.thumbnail} alt="" />
							{:else}
								<div class="ph">{TYPE_ICONS[c.content_type] || '📄'}</div>
							{/if}
						</div>
					{:else}
						<div class="thumb-port">
							{#if c.thumbnail}
								<img src={c.thumbnail} alt="" />
							{:else}
								<div class="ph">{TYPE_ICONS[c.content_type] || '📄'}</div>
							{/if}
						</div>
					{/if}
					<div class="info">
						<div class="title">
							{#if c.pinned}<span title="Prioritario">📌</span>{/if}
							{c.title}
						</div>
						<div class="meta">
							<span class="badge">{TYPE_LABELS[c.content_type]}</span>
							{#if c.collection}
								<span style="font-size:10px; color:var(--text-muted);">📁 {c.collection}</span>
							{/if}
							{#if c.content_type === 'series'}
								{#if c.seasons && c.seasons > 0}<span>📺 {c.seasons}T</span>{/if}
								{#if c.episode_count && c.episode_count > 0}<span>{c.episode_count} ep</span>{/if}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}/ep</span>{/if}
								{#if c.next_episode_date}
									{@const epDate = new Date(c.next_episode_date)}
									{@const aired = epDate < new Date()}
									<span class="next-ep" class:aired title="Próximo episodio">{aired ? '⏰' : '🟢'} {epDate.toLocaleDateString('es',{day:'numeric',month:'short'})}</span>
								{/if}
							{:else}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}</span>{/if}
								{#if c.content_type === 'book' && c.page_count && Number(c.page_count) > 0}
									<span>📚 {c.page_count} pág</span>
								{/if}
							{/if}
							{#if c.author}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:110px;">{c.author}</span>{/if}
						</div>
						{#if c.content_type === 'series' && c.episode_count && c.episode_count > 0 && c.duration_minutes > 0}
							<div style="font-size:11px; font-weight:600; color:var(--series);">~{formatDuration(c.duration_minutes * c.episode_count)} en total</div>
						{/if}

						{#if c.notes}
							<div style="font-size:11px; color:var(--text-muted); font-style:italic; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;" title={c.notes}>{c.notes}</div>
						{/if}

						<!-- Progress -->
						{#if c.content_type !== 'music'}
							{#if editingProgressId === c.id}
								<div class="progress-edit-wrap">
									<span class="progress-edit-label">{progressInputLabel(c)}</span>
									<div class="progress-edit-row">
										<!-- svelte-ignore a11y_autofocus --><input
											type="number"
											bind:value={progressValue}
											min="0"
											class="text progress-input"
											onblur={() => saveProgress(c)}
											onkeydown={(e) => e.key === 'Enter' && saveProgress(c)}
											autofocus
										/>
										<button class="btn" onclick={() => saveProgress(c)}>✓</button>
									</div>
									{#if progressValue > 0}
										<span style="font-size:10px; color:var(--game);">
											≈ {formatDuration(remainingMinutes({ ...c, progress: Math.floor(progressValue) }))} restante
										</span>
									{/if}
								</div>
							{:else}
								<button class="progress-track-btn" onclick={() => startEditProgress(c)} title={hasProgress ? 'Editar progreso' : 'Añadir progreso'}>
									<div class="progress-track" style="flex:1; margin:0;">
										<div class="progress-fill" style="width:{pct}%; background:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}; box-shadow:0 0 8px {TYPE_COLOR[c.content_type] ?? 'var(--primary)'};"></div>
									</div>
									{#if hasProgress}
										<span style="font-size:10px; color:var(--text-muted); white-space:nowrap;">{progressLabel(c)}</span>
										{#if remaining < (c.content_type === 'series' && c.episode_count ? c.duration_minutes * c.episode_count : c.duration_minutes)}
											<span style="font-size:10px; color:var(--text-dim); white-space:nowrap;">· {formatDuration(remaining)} restante</span>
										{/if}
									{:else}
										<span style="font-size:10px; color:var(--text-dim);">+ progreso</span>
									{/if}
								</button>
							{/if}
						{/if}

						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn">Abrir</button>
								</a>
							{/if}
							{#if c.url}
								<button
									class="btn"
									onclick={() => refresh(c)}
									disabled={refreshingId !== null}
									title="Actualizar metadatos"
									style={refreshingId === c.id ? 'animation: spin 0.8s linear infinite; opacity:0.7;' : ''}
								>↻</button>
							{/if}
							<button
								class="btn"
								class:pin-active={c.pinned}
								onclick={() => togglePin(c)}
								title={c.pinned ? 'Quitar prioridad' : 'Marcar prioritario'}
								style="opacity:{c.pinned ? 1 : 0.5};"
							>{c.pinned ? '📌' : '📍'}</button>
							<button class="btn" onclick={() => startEdit(c)} title="Editar">✏️</button>
							<button class="btn btn-consume" onclick={() => consume(c.id)} title="Marcar como consumido">✓</button>
							<button class="btn btn-abandon" onclick={() => abandon(c.id)} title="Abandonar">🚫</button>
							{#if deletingId === c.id}
								<span style="display:flex; gap:4px;">
									<button class="btn btn-danger" onclick={() => remove(c.id)}>Sí</button>
									<button class="btn" onclick={() => deletingId = null}>No</button>
								</span>
							{:else}
								<button class="btn btn-danger" onclick={() => deletingId = c.id}>✕</button>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if contents.length < total}
			<div class="center mt16">
				<button class="btn btn-lg" onclick={loadMore} disabled={loadingMore}>
					{loadingMore ? 'Cargando…' : `Cargar más (${total - contents.length} restantes)`}
				</button>
			</div>
		{/if}
	{/if}

	<!-- Mobile FAB (hidden on desktop) -->
	<button class="fab" onclick={() => showAdd = true}>+</button>
	<!-- Desktop FAB pill (hidden on mobile) -->
	<button class="desk-fab" onclick={() => showAdd = true}>
		<span class="plus">+</span> Añadir contenido
	</button>

	<!-- Edit modal -->
	{#if editingItem}
		<div class="overlay" onclick={() => editingItem = null} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal glass-strong" onclick={e => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-handle"></div>
				<h2>Editar</h2>
				<div class="field">
					<label for="edit-title">Título</label>
					<input id="edit-title" class="text" bind:value={editTitle} />
				</div>
				<div class="field">
					<label for="edit-author">Autor / Canal / Estudio</label>
					<input id="edit-author" class="text" bind:value={editAuthor} />
				</div>
				<div class="field">
					<label for="edit-url">URL</label>
					<input id="edit-url" class="text" bind:value={editUrl} placeholder="https://…" />
				</div>
				<div class="field">
					<label for="edit-duration">Duración{editingItem.content_type === 'series' ? ' por episodio' : ''} (minutos)</label>
					<input id="edit-duration" class="text" type="number" bind:value={editDuration} min="0" />
				</div>
				{#if editingItem.content_type === 'book'}
					<div class="field">
						<label for="edit-pages">Páginas</label>
						<input id="edit-pages" class="text" type="number" bind:value={editPageCount} min="0" />
					</div>
				{/if}
				{#if editingItem.content_type === 'series'}
					<div class="row">
						<div class="field" style="flex:1;">
							<label for="edit-seasons">Temporadas</label>
							<input id="edit-seasons" class="text" type="number" bind:value={editSeasons} min="0" />
						</div>
						<div class="field" style="flex:1;">
							<label for="edit-episodes">Episodios</label>
							<input id="edit-episodes" class="text" type="number" bind:value={editEpisodeCount} min="0" />
						</div>
					</div>
				{/if}
				<div class="field">
					<label for="edit-collection">Colección</label>
					<input id="edit-collection" class="text" bind:value={editCollection} list="collections-list" placeholder="Sin colección" />
					<datalist id="collections-list">
						{#each collections as col}
							<option value={col}></option>
						{/each}
					</datalist>
				</div>
				<div class="field">
					<label for="edit-thumbnail">URL de imagen</label>
					<input id="edit-thumbnail" class="text" bind:value={editThumbnail} placeholder="https://…" />
				</div>
				<div class="field">
					<label for="edit-notes">Notas</label>
					<textarea id="edit-notes" class="text" bind:value={editNotes}></textarea>
				</div>
				<div class="field">
					<label style="display:flex; align-items:center; gap:8px; text-transform:none; font-size:13px; cursor:pointer;">
						<input type="checkbox" bind:checked={editPinned} />
						Marcar como prioritario 📌
					</label>
				</div>
				{#if editError}<p class="error-msg">{editError}</p>{/if}
				<div class="row mt16">
					<button class="btn btn-primary btn-lg" onclick={saveEdit} style="flex:1; justify-content:center;">Guardar</button>
					<button class="btn btn-lg" onclick={() => editingItem = null} style="flex:1; justify-content:center;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Add modal -->
	{#if showAdd}
		<div class="overlay" onclick={() => showAdd = false} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal glass-strong" onclick={e => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-handle"></div>
				<h2>Añadir contenido</h2>
				<div class="field">
					<label for="add-url">URL (pega un enlace para autodetectar)</label>
					<div class="row">
						<input id="add-url" class="text" bind:value={addUrl} placeholder="https://..." style="flex:1;" />
						<button class="btn" onclick={() => lookupUrl()} disabled={lookupLoading}>
							{lookupLoading ? '…' : '🔍'}
						</button>
					</div>
					{#if lookupLoading}
						<p class="lookup-status" aria-live="polite">
							<span class="lookup-dot" aria-hidden="true"></span>
							Buscando información del enlace...
						</p>
					{/if}
					{#if duplicateChecked && duplicateItem}
						<div class="dup-banner" class:dup-pending={!duplicateItem.consumed && !duplicateItem.abandoned} class:dup-consumed={duplicateItem.consumed || duplicateItem.abandoned}>
							{#if !duplicateItem.consumed && !duplicateItem.abandoned}
								⚠️ Ya está en tu bóveda como pendiente: <strong>"{duplicateItem.title}"</strong>
							{:else}
								ℹ️ Ya lo {duplicateItem.consumed ? 'consumiste' : 'abandonaste'}{duplicateItem.times_consumed && duplicateItem.times_consumed > 1 ? ' ' + duplicateItem.times_consumed + ' veces' : ' una vez'}. Puedes añadirlo de nuevo.
							{/if}
						</div>
					{/if}
					{#if addWatchProviders.length > 0}
						<div class="providers-row">
							<span class="providers-label">Disponible en:</span>
							{#each addWatchProviders.slice(0, 6) as p}
								<div class="provider-chip" title={p.provider_name}>
									{#if p.logo_path}
										<img src={p.logo_path} alt={p.provider_name} class="provider-logo" />
									{:else}
										<span style="font-size:10px; padding: 2px 6px;">{p.provider_name}</span>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</div>
				<div class="field">
					<label for="add-type">Tipo</label>
					<select id="add-type" class="text" bind:value={addType}>
						<option value="youtube">▶️ YouTube</option>
						<option value="movie">🎬 Película</option>
						<option value="series">📺 Serie</option>
						<option value="music">🎵 Música</option>
						<option value="book">📖 Libro</option>
						<option value="game">🎮 Juego</option>
					</select>
				</div>
				<div class="field">
					<label for="add-title">Título</label>
					<input id="add-title" class="text" bind:value={addTitle} required />
				</div>
				<div class="field">
					<label for="add-author">Autor / Canal / Estudio</label>
					<input id="add-author" class="text" bind:value={addAuthor} />
				</div>
				<div class="field">
					<label for="add-duration">Duración{addType === 'series' ? ' por episodio' : ''} (minutos)</label>
					<input id="add-duration" class="text" type="number" bind:value={addDuration} min="0" />
				</div>
				{#if addType === 'series'}
					<div class="row">
						<div class="field" style="flex:1;">
							<label for="add-seasons">Temporadas</label>
							<input id="add-seasons" class="text" type="number" bind:value={addSeasons} min="0" />
						</div>
						<div class="field" style="flex:1;">
							<label for="add-episodes">Episodios totales</label>
							<input id="add-episodes" class="text" type="number" bind:value={addEpisodeCount} min="0" />
						</div>
					</div>
					{#if addDuration > 0 && addEpisodeCount > 0}
						<p class="muted" style="font-size:13px; margin-top:-4px;">
							Duración total estimada: ~{formatDuration(addDuration * addEpisodeCount)}
						</p>
					{/if}
					{#if addNextEpisodeDate}
						<p class="muted" style="font-size:12px; margin-top:-4px;">
							🟢 Próximo ep: {new Date(addNextEpisodeDate + 'T00:00:00').toLocaleDateString('es', {day:'numeric',month:'long',year:'numeric'})}
						</p>
					{/if}
				{/if}
				{#if addType === 'book'}
					<div class="field">
						<label for="add-book-format">Formato</label>
						<select id="add-book-format" class="text" bind:value={addBookFormat} onchange={() => {
							if (addBookFormat === 'manga') addWordsPerPage = 50;
							else addWordsPerPage = readingWordsPerPage;
						}}>
							<option value="book">Libro</option>
							<option value="manga">Manga / Comic</option>
						</select>
					</div>
					<div class="field">
						<label for="add-words-per-page">Palabras por página</label>
						<input id="add-words-per-page" class="text" type="number" bind:value={addWordsPerPage} min="1" />
					</div>
					<div class="field">
						<label for="add-pages">Páginas</label>
						<input id="add-pages" class="text" type="number" bind:value={addPageCount} min="0" />
					</div>
				{/if}
				<div class="field">
					<label for="add-collection">Colección</label>
					<input id="add-collection" class="text" bind:value={addCollection} list="collections-list-add" placeholder="Sin colección" />
					<datalist id="collections-list-add">
						{#each collections as col}
							<option value={col}></option>
						{/each}
					</datalist>
				</div>
				<div class="field">
					<label for="add-notes">Notas</label>
					<textarea id="add-notes" class="text" bind:value={addNotes}></textarea>
				</div>
				<!-- Toggles: prioritario + ya consumido -->
				<div class="toggle-row">
					<button
						class="toggle-btn"
						class:toggle-on={addPinned}
						onclick={() => addPinned = !addPinned}
						type="button"
					>
						<span class="toggle-ico">📌</span>
						<span>Prioritario</span>
					</button>
					<button
						class="toggle-btn toggle-btn-consume"
						class:toggle-on={addAlreadyConsumed}
						onclick={() => addAlreadyConsumed = !addAlreadyConsumed}
						type="button"
					>
						<span class="toggle-ico">✅</span>
						<span>Ya consumido</span>
					</button>
				</div>
				{#if addError}<p class="error-msg">{addError}</p>{/if}
				<div class="row mt16">
					<button class="btn btn-primary btn-lg" onclick={submitAdd} style="flex:1; justify-content:center;">Guardar</button>
					<button class="btn btn-lg" onclick={() => { showAdd = false; resetForm(); }} style="flex:1; justify-content:center;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}

	{#if showSettings}
		<div class="overlay" onclick={() => showSettings = false} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal glass-strong" onclick={e => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-handle"></div>
				<h2>Ajustes</h2>
				<div class="field">
					<label for="reading-wpm">Velocidad de lectura (palabras/minuto)</label>
					<input id="reading-wpm" class="text" type="number" bind:value={readingWpm} min="50" max="2000" />
				</div>
				<div class="row mt16">
					<button class="btn btn-primary btn-lg" onclick={saveSettings} style="flex:1; justify-content:center;">Guardar</button>
					<button class="btn btn-lg" onclick={() => { showSettings = false; }} style="flex:1; justify-content:center;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	.progress-track-btn {
		all: unset;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		margin: 2px 0;
		padding: 2px 0;
	}
	.progress-edit-wrap {
		margin: 2px 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.progress-edit-label {
		font-size: 10px;
		color: var(--text-muted);
	}
	.progress-edit-row {
		display: flex;
		gap: 6px;
		align-items: center;
	}
	.progress-input {
		flex: 1;
		font-size: 13px;
		padding: 6px 10px !important;
		min-width: 0;
	}

	/* Duplicate banner */
	.dup-banner {
		display: flex;
		gap: 6px;
		padding: 9px 12px;
		border-radius: 10px;
		font-size: 12px;
		margin: 6px 0 2px;
		border: 1px solid;
		flex-wrap: wrap;
		align-items: center;
	}
	.dup-pending {
		background: oklch(0.25 0.08 45 / 0.4);
		border-color: oklch(0.65 0.18 45 / 0.5);
		color: oklch(0.85 0.12 45);
	}
	.dup-consumed {
		background: var(--glass-bg-weak);
		border-color: var(--glass-border);
		color: var(--text-muted);
	}

	/* Watch providers */
	.providers-row {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		margin: 6px 0 2px;
	}
	.providers-label {
		font-size: 11px;
		color: var(--text-muted);
	}
	.provider-chip {
		border-radius: 6px;
		overflow: hidden;
		border: 1px solid var(--glass-border);
	}
	.provider-logo {
		width: 32px;
		height: 32px;
		display: block;
	}

	/* Next episode badge on cards */
	.next-ep {
		font-size: 10px;
		font-weight: 600;
		color: var(--series);
	}
	.next-ep.aired {
		color: var(--text-dim);
	}
</style>
