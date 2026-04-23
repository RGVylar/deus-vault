<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
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

	// Landscape layout: video content has 16:9 thumbnails → show them at top, full width
	function isLandscape(type: ContentType): boolean {
		return type === 'youtube' || type === 'movie' || type === 'series';
	}

	// For portrait cards (books, games, music)
	function thumbClass(type: ContentType): string {
		return type === 'game' ? 'thumb thumb-top' : 'thumb';
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
	let addWordsPerPage = $state(readingWordsPerPage);
	let addBookFormat: 'book' | 'manga' = $state('book');
	let addEpisodeCount = $state(0);
	let addSeasons = $state(0);
	let addAuthor = $state('');
	let addNotes = $state('');
	let addThumbnail = $state('');
	let addSourceId = $state('');
	let addCollection = $state('');
	let addPinned = $state(false);
	let addError = $state('');
	let lookupLoading = $state(false);
	let lastLookupUrl = $state('');
	let refreshingId = $state<number | null>(null);
	let autoLookupTimer: ReturnType<typeof setTimeout> | null = null;
	let searchTimer: ReturnType<typeof setTimeout> | null = null;

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
	function isLookupCandidate(url: string): boolean {
		try {
			const h = new URL(url).hostname.toLowerCase();
			return h.includes('youtube.com') || h.includes('youtu.be') ||
				h.includes('store.steampowered.com') || h.includes('netflix.com') ||
				h.includes('primevideo.com') || h.includes('amazon.com') ||
				h.includes('max.com') || h.includes('hbomax.com') ||
				h.includes('disneyplus.com') || h.includes('strem.io') ||
				h.includes('stremio.com') || h.includes('open.spotify.com') ||
				h.includes('openlibrary.org') || h.includes('goodreads.com') ||
				h.includes('books.google.com');
		} catch { return false; }
	}

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
		} catch (e: unknown) {
			addError = e instanceof Error ? e.message : 'Lookup failed';
		} finally { lookupLoading = false; }
	}

	async function submitAdd() {
		addError = '';
		try {
			await api.post('/contents', {
				title: addTitle, content_type: addType, url: addUrl || null,
				thumbnail: addThumbnail || null, duration_minutes: addDuration,
				page_count: addPageCount && Number(addPageCount) > 0 ? Number(addPageCount) : null,
				words_per_page: addWordsPerPage && Number(addWordsPerPage) > 0 ? Number(addWordsPerPage) : null,
				episode_count: addType === 'series' && addEpisodeCount > 0 ? addEpisodeCount : null,
				seasons: addType === 'series' && addSeasons > 0 ? addSeasons : null,
				source_id: addSourceId || null, author: addAuthor || null, notes: addNotes || null,
				collection: addCollection.trim() || null, pinned: addPinned,
			});
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
		addNotes = ''; addThumbnail = ''; addSourceId = ''; addType = 'youtube';
		addPageCount = 0; addWordsPerPage = readingWordsPerPage; addBookFormat = 'book';
		addEpisodeCount = 0; addSeasons = 0; lastLookupUrl = '';
		addCollection = ''; addPinned = false;
	}

	async function consume(id: number) { await api.post(`/contents/${id}/consume`); load(); }
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
	<p>Redirigiendo…</p>
{:else}
	{#if stats}
		<div class="hero-number ominous">
			<div class="kicker">DEUDA DE CONTENIDO</div>
			<div class="number">{formatHeroTime(stats.total_pending_minutes)}</div>
			<div class="unit">{formatDuration(stats.total_pending_minutes)} totales por consumir</div>
		</div>

		<div class="stat-row">
			<div class="stat-pill">
				<span>📦</span> <span class="val">{stats.pending_count}</span> pendientes
			</div>
			<div class="stat-pill">
				<span>✅</span> <span class="val">{stats.consumed_count}</span> consumidos
			</div>
		</div>

		{#if Object.keys(stats.by_type).length > 0}
			<div class="stat-row">
				{#each Object.entries(stats.by_type) as [type, mins]}
					{@const pct = totalByTypeMins > 0 ? (mins / totalByTypeMins) * 100 : 0}
					<div class="stat-pill stat-pill-typed" style="--pill-color:{TYPE_COLOR[type] ?? 'var(--primary)'}">
						<span>{TYPE_ICONS[type] || '📄'}</span>
						<span class="val">{formatDuration(mins)}</span>
						{TYPE_LABELS[type] || type}
						<span class="stat-pill-bar" style="width:{pct}%"></span>
					</div>
				{/each}
			</div>
		{/if}
	{/if}

	<!-- Filter tabs + Search -->
	<div class="tabs">
		<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️ YouTube</button>
		<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬 Películas</button>
		<button class:btn-secondary={filter !== 'series'} onclick={() => filter = 'series'}>📺 Series</button>
		<button class:btn-secondary={filter !== 'music'} onclick={() => filter = 'music'}>🎵 Música</button>
		<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖 Libros</button>
		<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮 Juegos</button>
	</div>

	<div class="search-sort-row">
		<div class="search-wrap" style="flex:1;">
			<input
				type="search"
				bind:value={searchQuery}
				placeholder="🔍  Buscar…"
				class="search-input"
			/>
			{#if searchQuery}
				<button class="search-clear" onclick={() => searchQuery = ''} aria-label="Limpiar">✕</button>
			{/if}
		</div>
		<select bind:value={sortOrder} class="sort-select">
			<option value="recent">📅 Recientes</option>
			<option value="duration_asc">⏱ Duración ↑</option>
			<option value="duration_desc">⏱ Duración ↓</option>
			<option value="title_asc">🔤 Título A–Z</option>
		</select>
	</div>

	<!-- Collection filter chips -->
	{#if collections.length > 0}
		<div class="collection-chips">
			<button
				class="col-chip"
				class:col-chip-active={activeCollection === null}
				onclick={() => activeCollection = null}
			>Todas</button>
			{#each collections as col}
				<button
					class="col-chip"
					class:col-chip-active={activeCollection === col}
					onclick={() => activeCollection = activeCollection === col ? null : col}
				>📁 {col}</button>
			{/each}
		</div>
	{/if}

	<!-- Content list -->
	{#if loading}
		<p style="text-align:center; color:var(--text-muted);">Cargando…</p>
	{:else if contents.length === 0}
		<div class="card" style="text-align:center; padding:2rem;">
			<p style="font-size:1.2rem; margin-bottom:0.5rem;">🏛️</p>
			<p style="color:var(--text-muted);">
				{searchQuery ? 'Sin resultados para "' + searchQuery + '"' : 'La bóveda está vacía. ¡Añade contenido!'}
			</p>
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
					class="content-card"
					class:card-landscape={landscape}
					style="--card-accent:{TYPE_COLOR[c.content_type] ?? 'var(--border)'}"
				>
					{#if landscape}
						<!-- Landscape: thumbnail banner at top -->
						<div class="thumb-landscape">
							{#if c.thumbnail}
								<img src={c.thumbnail} alt="" />
							{:else}
								<div class="thumb-landscape-ph">{TYPE_ICONS[c.content_type] || '📄'}</div>
							{/if}
						</div>
					{:else}
						<!-- Portrait: thumbnail side column (books, games, music) -->
						{#if c.thumbnail}
							<img class={thumbClass(c.content_type)} src={c.thumbnail} alt="" />
						{:else}
							<div class="{thumbClass(c.content_type)} thumb-placeholder">
								{TYPE_ICONS[c.content_type] || '📄'}
							</div>
						{/if}
					{/if}
					<div class="info">
						<div class="title">
							{#if c.pinned}<span class="pin-indicator" title="Prioritario">📌</span>{/if}
							{c.title}
						</div>
						<div class="meta">
							<span class="badge {c.content_type}">{TYPE_LABELS[c.content_type]}</span>
							{#if c.collection}
								<span class="collection-badge">📁 {c.collection}</span>
							{/if}
							{#if c.content_type === 'series'}
								{#if c.seasons && c.seasons > 0}<span>📺 {c.seasons}T</span>{/if}
								{#if c.episode_count && c.episode_count > 0}<span>{c.episode_count} ep</span>{/if}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}/ep</span>{/if}
							{:else}
								{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}</span>{/if}
								{#if c.content_type === 'book' && c.page_count && Number(c.page_count) > 0}
									<span>📚 {c.page_count} pág</span>
								{/if}
							{/if}
							{#if c.author}<span class="author-meta">{c.author}</span>{/if}
						</div>
						{#if c.content_type === 'series' && c.episode_count && c.episode_count > 0 && c.duration_minutes > 0}
							<div class="series-total">~{formatDuration(c.duration_minutes * c.episode_count)} en total</div>
						{/if}

						<!-- Notes snippet -->
						{#if c.notes}
							<div class="notes-snippet" title={c.notes}>{c.notes}</div>
						{/if}

						<!-- Progress bar (always visible for non-music) -->
						{#if c.content_type !== 'music'}
							{#if editingProgressId === c.id}
								<div class="progress-edit-wrap">
									<span class="progress-edit-label">{progressInputLabel(c)}</span>
									<div class="progress-edit-row">
										<input
											type="number"
											bind:value={progressValue}
											min="0"
											class="progress-input"
											onblur={() => saveProgress(c)}
											onkeydown={(e) => e.key === 'Enter' && saveProgress(c)}
											autofocus
										/>
										<button class="btn-secondary progress-save-btn" onclick={() => saveProgress(c)}>✓</button>
									</div>
									{#if progressValue > 0}
										<span class="progress-preview">
											≈ {formatDuration(remainingMinutes({ ...c, progress: Math.floor(progressValue) }))} restante
										</span>
									{/if}
								</div>
							{:else}
								<button class="progress-track-btn" onclick={() => startEditProgress(c)} title={hasProgress ? 'Editar progreso' : 'Añadir progreso'}>
									<div class="progress-bar-bg">
										<div class="progress-bar-fg" style="width:{pct}%; background:{TYPE_COLOR[c.content_type] ?? 'var(--primary)'}"></div>
									</div>
									{#if hasProgress}
										<span class="progress-label-txt">{progressLabel(c)}</span>
										{#if remaining < (c.content_type === 'series' && c.episode_count ? c.duration_minutes * c.episode_count : c.duration_minutes)}
											<span class="progress-remaining">· {formatDuration(remaining)} restante</span>
										{/if}
									{:else}
										<span class="progress-add-txt">+ progreso</span>
									{/if}
								</button>
							{/if}
						{/if}

						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn-secondary">Abrir</button>
								</a>
							{/if}
							{#if c.url}
								<button
									class="btn-secondary"
									onclick={() => refresh(c)}
									disabled={refreshingId !== null}
									title="Actualizar metadatos"
									style={refreshingId === c.id ? 'animation: spin 0.8s linear infinite; opacity:0.7;' : ''}
								>↻</button>
							{/if}
							<!-- Pin toggle -->
							<button
								class="btn-secondary pin-btn"
								class:pin-btn-active={c.pinned}
								onclick={() => togglePin(c)}
								title={c.pinned ? 'Quitar prioridad' : 'Marcar prioritario'}
							>{c.pinned ? '📌' : '📍'}</button>
							<!-- Edit -->
							<button class="btn-secondary" onclick={() => startEdit(c)} title="Editar">✏️</button>
							<!-- Consume -->
							<button onclick={() => consume(c.id)} style="background:rgba(79,255,170,0.15); color:var(--game); box-shadow:none;">✓</button>
							<!-- Delete (with confirm) -->
							{#if deletingId === c.id}
								<span class="delete-confirm">
									<button class="btn-danger" onclick={() => remove(c.id)}>Sí</button>
									<button class="btn-secondary" onclick={() => deletingId = null}>No</button>
								</span>
							{:else}
								<button class="btn-danger" onclick={() => deletingId = c.id}>✕</button>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if contents.length < total}
			<div style="text-align:center; margin: 1rem 0 2rem;">
				<button class="btn-secondary" onclick={loadMore} disabled={loadingMore}>
					{loadingMore ? 'Cargando…' : `Cargar más (${total - contents.length} restantes)`}
				</button>
			</div>
		{/if}
	{/if}

	<button class="fab settings" onclick={() => showSettings = true} title="Ajustes">⚙️</button>
	<button class="fab" onclick={() => showAdd = true}>+</button>

	<!-- Edit modal -->
	{#if editingItem}
		<div class="overlay" onclick={() => editingItem = null} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal" onclick={e => e.stopPropagation()} role="dialog">
				<h2>Editar</h2>
				<div class="form-group">
					<label for="edit-title">Título</label>
					<input id="edit-title" bind:value={editTitle} />
				</div>
				<div class="form-group">
					<label for="edit-author">Autor / Canal / Estudio</label>
					<input id="edit-author" bind:value={editAuthor} />
				</div>
				<div class="form-group">
					<label for="edit-url">URL</label>
					<input id="edit-url" bind:value={editUrl} placeholder="https://…" />
				</div>
				<div class="form-group">
					<label for="edit-duration">Duración{editingItem.content_type === 'series' ? ' por episodio' : ''} (minutos)</label>
					<input id="edit-duration" type="number" bind:value={editDuration} min="0" />
				</div>
				{#if editingItem.content_type === 'book'}
					<div class="form-group">
						<label for="edit-pages">Páginas</label>
						<input id="edit-pages" type="number" bind:value={editPageCount} min="0" />
					</div>
				{/if}
				{#if editingItem.content_type === 'series'}
					<div style="display:flex; gap:0.75rem;">
						<div class="form-group" style="flex:1;">
							<label for="edit-seasons">Temporadas</label>
							<input id="edit-seasons" type="number" bind:value={editSeasons} min="0" />
						</div>
						<div class="form-group" style="flex:1;">
							<label for="edit-episodes">Episodios</label>
							<input id="edit-episodes" type="number" bind:value={editEpisodeCount} min="0" />
						</div>
					</div>
				{/if}
				<div class="form-group">
					<label for="edit-collection">Colección</label>
					<input id="edit-collection" bind:value={editCollection} list="collections-list" placeholder="Sin colección" />
					<datalist id="collections-list">
						{#each collections as col}
							<option value={col}></option>
						{/each}
					</datalist>
				</div>
				<div class="form-group">
					<label for="edit-thumbnail">URL de imagen</label>
					<input id="edit-thumbnail" bind:value={editThumbnail} placeholder="https://…" />
				</div>
				<div class="form-group">
					<label for="edit-notes">Notas</label>
					<textarea id="edit-notes" bind:value={editNotes}></textarea>
				</div>
				<div class="form-group pinned-row">
					<label class="pinned-label">
						<input type="checkbox" bind:checked={editPinned} />
						Marcar como prioritario 📌
					</label>
				</div>
				{#if editError}<p class="error">{editError}</p>{/if}
				<div style="display:flex; gap:0.5rem; margin-top:1rem;">
					<button onclick={saveEdit} style="flex:1;">Guardar</button>
					<button class="btn-secondary" onclick={() => editingItem = null} style="flex:1;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Add modal -->
	{#if showAdd}
		<div class="overlay" onclick={() => showAdd = false} role="presentation">
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<div class="modal" onclick={e => e.stopPropagation()} role="dialog">
				<h2>Añadir contenido</h2>
				<div class="form-group">
					<label for="add-url">URL (pega un enlace para autodetectar)</label>
					<div style="display:flex; gap:0.5rem;">
						<input id="add-url" bind:value={addUrl} placeholder="https://..." style="flex:1;" />
						<button class="btn-secondary" onclick={() => lookupUrl()} disabled={lookupLoading} style="white-space:nowrap;">
							{lookupLoading ? '…' : '🔍'}
						</button>
					</div>
					{#if lookupLoading}
						<p class="lookup-status" aria-live="polite">
							<span class="lookup-dot" aria-hidden="true"></span>
							Buscando información del enlace...
						</p>
					{/if}
				</div>
				<div class="form-group">
					<label for="add-type">Tipo</label>
					<select id="add-type" bind:value={addType}>
						<option value="youtube">▶️ YouTube</option>
						<option value="movie">🎬 Película</option>
						<option value="series">📺 Serie</option>
						<option value="music">🎵 Música</option>
						<option value="book">📖 Libro</option>
						<option value="game">🎮 Juego</option>
					</select>
				</div>
				<div class="form-group">
					<label for="add-title">Título</label>
					<input id="add-title" bind:value={addTitle} required />
				</div>
				<div class="form-group">
					<label for="add-author">Autor / Canal / Estudio</label>
					<input id="add-author" bind:value={addAuthor} />
				</div>
				<div class="form-group">
					<label for="add-duration">Duración{addType === 'series' ? ' por episodio' : ''} (minutos)</label>
					<input id="add-duration" type="number" bind:value={addDuration} min="0" />
				</div>
				{#if addType === 'series'}
					<div style="display:flex; gap:0.75rem;">
						<div class="form-group" style="flex:1;">
							<label for="add-seasons">Temporadas</label>
							<input id="add-seasons" type="number" bind:value={addSeasons} min="0" />
						</div>
						<div class="form-group" style="flex:1;">
							<label for="add-episodes">Episodios totales</label>
							<input id="add-episodes" type="number" bind:value={addEpisodeCount} min="0" />
						</div>
					</div>
					{#if addDuration > 0 && addEpisodeCount > 0}
						<p style="font-size:0.85rem; color:var(--text-muted); margin-top:-0.25rem;">
							Duración total estimada: ~{formatDuration(addDuration * addEpisodeCount)}
						</p>
					{/if}
				{/if}
				{#if addType === 'book'}
					<div class="form-group">
						<label for="add-book-format">Formato</label>
						<select id="add-book-format" bind:value={addBookFormat} onchange={() => {
							if (addBookFormat === 'manga') addWordsPerPage = 50;
							else addWordsPerPage = readingWordsPerPage;
						}}>
							<option value="book">Libro</option>
							<option value="manga">Manga / Comic</option>
						</select>
					</div>
					<div class="form-group">
						<label for="add-words-per-page">Palabras por página</label>
						<input id="add-words-per-page" type="number" bind:value={addWordsPerPage} min="1" />
					</div>
					<div class="form-group">
						<label for="add-pages">Páginas</label>
						<input id="add-pages" type="number" bind:value={addPageCount} min="0" />
					</div>
				{/if}
				<div class="form-group">
					<label for="add-collection">Colección</label>
					<input id="add-collection" bind:value={addCollection} list="collections-list-add" placeholder="Sin colección" />
					<datalist id="collections-list-add">
						{#each collections as col}
							<option value={col}></option>
						{/each}
					</datalist>
				</div>
				<div class="form-group">
					<label for="add-notes">Notas</label>
					<textarea id="add-notes" bind:value={addNotes}></textarea>
				</div>
				<div class="form-group pinned-row">
					<label class="pinned-label">
						<input type="checkbox" bind:checked={addPinned} />
						Marcar como prioritario 📌
					</label>
				</div>
				{#if addError}<p class="error">{addError}</p>{/if}
				<div style="display:flex; gap:0.5rem; margin-top:1rem;">
					<button onclick={submitAdd} style="flex:1;">Guardar</button>
					<button class="btn-secondary" onclick={() => { showAdd = false; resetForm(); }} style="flex:1;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}

	{#if showSettings}
		<div class="overlay" onclick={() => showSettings = false} role="presentation">
			<div class="modal" onclick={e => e.stopPropagation()} role="dialog">
				<h2>Ajustes</h2>
				<div class="form-group">
					<label for="reading-wpm">Velocidad de lectura (palabras/minuto)</label>
					<input id="reading-wpm" type="number" bind:value={readingWpm} min="50" max="2000" />
				</div>
				<div style="display:flex; gap:0.5rem; margin-top:1rem;">
					<button onclick={saveSettings} style="flex:1;">Guardar</button>
					<button class="btn-secondary" onclick={() => { showSettings = false; }} style="flex:1;">Cancelar</button>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	/* Search + sort row */
	.search-sort-row {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		align-items: center;
	}
	.search-wrap {
		position: relative;
	}
	.search-input {
		width: 100%;
		padding-right: 2.2rem;
	}
	.search-clear {
		position: absolute;
		right: 0.5rem; top: 50%; transform: translateY(-50%);
		background: none; box-shadow: none; border: none;
		color: var(--text-muted); padding: 0.2rem 0.4rem;
		font-size: 0.8rem; border-radius: 6px;
	}
	.search-clear:hover { background: var(--surface); color: var(--text); }
	.sort-select {
		flex-shrink: 0;
		font-size: 0.78rem;
		padding: 0.5rem 0.6rem;
		border-radius: 10px;
		white-space: nowrap;
	}

	/* Collection chips */
	.collection-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-bottom: 0.75rem;
	}
	.col-chip {
		background: var(--surface2);
		border: 1px solid var(--border);
		color: var(--text-muted);
		box-shadow: none;
		padding: 0.25rem 0.65rem;
		font-size: 0.75rem;
		border-radius: 99px;
	}
	.col-chip:hover { background: var(--surface-hover); color: var(--text); box-shadow: none; }
	.col-chip-active {
		background: var(--primary-glow) !important;
		border-color: var(--primary) !important;
		color: var(--primary) !important;
		font-weight: 700;
	}

	/* Thumb placeholder */
	.thumb-placeholder {
		display: flex; align-items: center; justify-content: center;
		font-size: 1.8rem;
		background: var(--surface2);
	}

	/* Pin indicator */
	.pin-indicator {
		font-size: 0.75rem;
		margin-right: 0.2rem;
		vertical-align: middle;
	}

	/* Collection badge on card */
	.collection-badge {
		font-size: 0.68rem;
		background: rgba(255,255,255,0.07);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.05rem 0.35rem;
		color: var(--text-muted);
	}

	/* Notes snippet */
	.notes-snippet {
		font-size: 0.72rem;
		color: var(--text-muted);
		margin: 0.2rem 0 0.1rem;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		line-height: 1.35;
		font-style: italic;
	}

	/* Author meta truncated */
	.author-meta {
		overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
		max-width: 120px;
	}

	/* Pin button */
	.pin-btn { font-size: 0.85rem; padding: 0.25rem 0.4rem; opacity: 0.5; }
	.pin-btn:hover { opacity: 1; }
	.pin-btn-active { opacity: 1 !important; }

	/* Delete confirm */
	.delete-confirm {
		display: flex;
		gap: 0.25rem;
	}
	.delete-confirm button {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
	}

	/* Progress bar (always-visible track) */
	.progress-track-btn {
		all: unset;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		margin: 0.35rem 0 0.15rem;
		padding: 0.1rem 0;
	}
	.progress-bar-bg {
		flex-shrink: 0;
		width: 56px;
		height: 3px;
		background: rgba(255,255,255,0.1);
		border-radius: 2px;
		overflow: hidden;
	}
	.progress-bar-fg {
		height: 100%;
		border-radius: 2px;
		transition: width 0.3s;
		min-width: 2px;
	}
	.progress-label-txt {
		font-size: 0.72rem;
		color: var(--primary-dim);
		white-space: nowrap;
	}
	.progress-remaining {
		font-size: 0.7rem;
		color: var(--text-muted);
		white-space: nowrap;
	}
	.progress-add-txt {
		font-size: 0.7rem;
		color: var(--text-muted);
		opacity: 0.6;
	}
	.progress-track-btn:hover .progress-add-txt { opacity: 1; color: var(--primary-dim); }
	.progress-track-btn:hover .progress-bar-bg { background: rgba(255,255,255,0.18); }

	/* Progress edit mode */
	.progress-edit-wrap {
		margin: 0.35rem 0 0.15rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.progress-edit-label {
		font-size: 0.7rem;
		color: var(--text-muted);
	}
	.progress-edit-row {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	.progress-input {
		flex: 1;
		font-size: 0.82rem;
		padding: 0.3rem 0.5rem;
		min-width: 0;
	}
	.progress-save-btn {
		padding: 0.3rem 0.6rem;
		font-size: 0.8rem;
		flex-shrink: 0;
	}
	.progress-preview {
		font-size: 0.7rem;
		color: var(--game);
	}

	/* Pinned checkbox row */
	.pinned-row { margin-top: 0.25rem; }
	.pinned-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
		cursor: pointer;
	}
</style>
