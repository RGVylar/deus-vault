<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, typeLabel, buildConsumeUrl, releaseYear } from '$lib/utils';
	import Icon from '$lib/components/Icon.svelte';
	import RolodexRoller from '$lib/components/RolodexRoller.svelte';
	import { t, tc, type TKey } from '$lib/i18n/index.svelte';
	import {
		attention, attachAttentionLifecycle, beginAttention, endAttention, markLaunched, markDone,
		setTuning, resetAttention, rankedItems, topTraits, attentionLevel, hasSignal, tuningActive,
		pickTuned, suggestedFilters, formatAttention, TRAIT_KINDS, type TraitKind
	} from '$lib/stores/attention.svelte';
	import type { Content, ContentType } from '$lib/types';

	type TimePreset = { labelKey: TKey; min: number | null; max: number | null };
	const TIME_PRESETS: TimePreset[] = [
		{ labelKey: 'random.time.any',           min: null, max: null },
		{ labelKey: 'random.time.under30',       min: null, max: 30   },
		{ labelKey: 'random.time.about1h',       min: 30,   max: 90   },
		{ labelKey: 'random.time.about2h',       min: 90,   max: 150  },
		{ labelKey: 'random.time.freeAfternoon', min: 150,  max: null },
	];

	const TYPE_ICON: Record<string, string> = {
		youtube: 'play', movie: 'film', series: 'tv', music: 'music', book: 'book', manga: 'manga', game: 'game'
	};
	const TYPE_COLOR: Record<string, string> = {
		youtube: 'var(--youtube)', movie: 'var(--movie)', series: 'var(--series)',
		book: 'var(--book)', manga: 'var(--manga)', game: 'var(--game)', music: 'var(--music)'
	};
	const TYPES: { key: ContentType; icon: string }[] = [
		{ key: 'youtube', icon: 'play' }, { key: 'movie', icon: 'film' },
		{ key: 'series', icon: 'tv' },    { key: 'music', icon: 'music' },
		{ key: 'book', icon: 'book' },    { key: 'manga', icon: 'manga' },
		{ key: 'game', icon: 'game' },
	];

	let pick: Content | null = $state(null);
	let deckItems: Content[] = $state([]);
	let spinTokenCounter = $state(0);
	let selectedTypes = $state<ContentType[]>([]);   // multi-selección (vacío = cualquiera)
	let selectedPreset = $state(0);
	let showCustom = $state(false);
	let customMin = $state('');
	let customMax = $state('');
	let selectedGenres = $state<string[]>([]);       // multi-selección (vacío = cualquiera)
	let availableGenres = $state<string[]>([]);
	let matchCount = $state<number | null>(null);
	let error = $state('');
	let spinning = $state(false);

	let recent: Content[] = [];

	const hasResult = $derived(!!pick || !!error);
	const pickYear = $derived(pick ? releaseYear(pick) : null);
	const pickGenres = $derived((pick?.genres ?? '').split(',').map(g => g.trim()).filter(Boolean));

	/**
	 * Los géneros se pedían una sola vez y el error se tragaba en silencio: un
	 * fallo de red dejaba `availableGenres` vacío y el filtro de género
	 * desaparecía de la página el resto de la sesión, sin aviso. En móvil pasa
	 * mucho más (red inestable, arranque en frío, pestaña que despierta), así
	 * que reintenta y se cura solo.
	 */
	async function loadGenres(retries = 2) {
		try {
			availableGenres = await api.get<string[]>('/contents/genres');
		} catch {
			if (retries > 0) setTimeout(() => loadGenres(retries - 1), 1500);
		}
	}

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		loadGenres();
		// Cierra el tramo abierto al esconder la pestaña o al salir de Azar.
		return attachAttentionLifecycle();
	});

	// ── Tiempo de atención ──
	// El panel se reconstruye solo cuando cambian las entradas (cada tirada las
	// toca), así que basta con derivar de `attention.entries`.
	const attentionTop = $derived(rankedItems(4));
	const attentionMaxMs = $derived(attentionTop[0]?.ms ?? 0);
	const attentionTraits = $derived(
		TRAIT_KINDS
			.map(kind => ({ kind, scores: topTraits(kind, kind === 'genre' ? 3 : 2) }))
			.filter(row => row.scores.length > 0)
	);
	const showAttention = $derived(attentionTop.length > 0);
	let tunedPick = $state(false);   // el ganador de la última tirada salió pesado

	function traitLabel(kind: TraitKind, value: string): string {
		if (kind === 'type') return typeLabel(value);
		if (kind === 'decade') return t('random.attention.decadeValue', { value });
		return value;
	}

	/** Vuelca la afinidad en los filtros que el backend sí entiende. */
	function applyAttentionFilters() {
		const { genres, types } = suggestedFilters();
		selectedGenres = genres.filter(g => availableGenres.includes(g));
		selectedTypes = types;
	}

	function selectPreset(i: number) { selectedPreset = i; showCustom = false; customMin = ''; customMax = ''; }
	function toggleType(t: ContentType) { selectedTypes = selectedTypes.includes(t) ? selectedTypes.filter(x => x !== t) : [...selectedTypes, t]; }
	function toggleGenre(g: string) { selectedGenres = selectedGenres.includes(g) ? selectedGenres.filter(x => x !== g) : [...selectedGenres, g]; }

	function buildQuery(extraExcludeIds: number[] = []): string {
		const params = new URLSearchParams();
		for (const t of selectedTypes) params.append('content_type', t);
		if (showCustom) {
			if (customMin) params.set('min_duration', String(Math.max(0, Number(customMin))));
			if (customMax) params.set('max_duration', String(Math.max(0, Number(customMax))));
		} else {
			const p = TIME_PRESETS[selectedPreset];
			if (p.min != null) params.set('min_duration', String(p.min));
			if (p.max != null) params.set('max_duration', String(p.max));
		}
		for (const g of selectedGenres) params.append('genre', g);
		// Skip the last few picks so re-rolling doesn't keep landing on the same item.
		for (const c of recent.slice(0, 3)) params.append('exclude_id', String(c.id));
		for (const id of extraExcludeIds) params.append('exclude_id', String(id));
		const qs = params.toString();
		return qs ? '?' + qs : '';
	}

	$effect(() => {
		selectedTypes; selectedGenres; selectedPreset; showCustom; customMin; customMax;
		api.get<number>(`/contents/random/count${buildQuery()}`).then(n => matchCount = n).catch(() => matchCount = null);
	});

	// Cuántas cartas visualmente distintas queremos en el mazo que se ve girar
	// (además de la que gana). Se recorta al nº de items que realmente hay
	// disponibles, para no repetir pedidos de más cuando la lista es corta.
	const DECK_SIZE = 8;

	async function roll() {
		if (spinning) return;
		// Si la carga inicial de géneros no llegó, este es el mejor momento para
		// recuperarla: el usuario está justo en la pantalla donde hacen falta.
		if (availableGenres.length === 0) void loadGenres(1);
		// Volver a tirar cierra el tiempo de atención del contenido anterior:
		// el rato del giro no cuenta, porque ahí ya no se está mirando la ficha.
		endAttention();
		error = '';
		spinning = true;
		try {
			const deckSize = matchCount != null ? Math.max(1, Math.min(DECK_SIZE, matchCount)) : DECK_SIZE;
			const collected: Content[] = [];
			for (let i = 0; i < deckSize; i++) {
				const item = await api.get<Content>(`/contents/random${buildQuery(collected.map(c => c.id))}`);
				collected.push(item);
			}
			deckItems = collected;
			// El backend ya ha sorteado los candidatos; el afinado sólo decide
			// cuál de ellos gana, pesando por los rasgos que más te frenan.
			const winner = pickTuned(collected);
			tunedPick = tuningActive();
			pick = winner;
			recent = [winner, ...recent.filter(c => c.id !== winner.id)].slice(0, 6);
			spinTokenCounter++; // dispara el giro del RolodexRoller hacia `winner`
		} catch (e: unknown) {
			pick = null;
			error = e instanceof Error ? e.message : t('errors.generic');
			spinning = false;
		}
	}

	function handleSettled() {
		spinning = false;
		// El cronómetro arranca cuando el rolodex se para y la ficha ya es legible.
		if (pick) beginAttention(pick);
	}

	async function consume(id: number) {
		markDone(id);
		await api.post(`/contents/${id}/consume`);
		pick = null;
	}
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">{t('random.redirecting')}</p>
{:else}

<!-- Desktop topbar -->
<div class="desk-topbar desk-only">
	<h1 class="desk-title">{t('random.title')}</h1>
	<div class="desk-spacer"></div>
</div>

<div class="azar">

	<!-- Título móvil -->
	<div class="azar-head">
		<h1>{t('random.title')}</h1>
		<p>{t('random.subtitle')}</p>
	</div>

	<!-- ── Filtros ── -->
	<div class="azar-filters">
		<div class="flt-block">
			<p class="flt-label"><Icon name="layers" size={14} /> {t('random.filters.type')}</p>
			<div class="type-row">
				<button class="type-btn all" class:active={selectedTypes.length === 0} onclick={() => selectedTypes = []}>{t('random.filters.all')}</button>
				{#each TYPES as t2}
					<button class="type-btn" class:active={selectedTypes.includes(t2.key)}
						style="--tc:{TYPE_COLOR[t2.key]}" onclick={() => toggleType(t2.key)} aria-label={typeLabel(t2.key)}>
						<Icon name={t2.icon} size={21} />
					</button>
				{/each}
			</div>
		</div>

		<div class="flt-block">
			<p class="flt-label"><Icon name="clock" size={14} /> {t('random.filters.time')}</p>
			<div class="chip-row">
				{#each TIME_PRESETS as preset, i}
					<button class="tab" class:active={!showCustom && selectedPreset === i} onclick={() => selectPreset(i)}>{t(preset.labelKey)}</button>
				{/each}
				<button class="tab" class:active={showCustom} onclick={() => { showCustom = true; selectedPreset = -1; }}>{t('random.filters.exact')}</button>
			</div>
			{#if showCustom}
				<div class="custom-range show">
					<div class="row">
						<div class="field" style="flex:1; margin:0;">
							<label for="r-min">{t('random.filters.min')}</label>
							<input id="r-min" class="text" type="number" bind:value={customMin} min="0" placeholder="0" />
						</div>
						<span class="muted" style="padding-top:24px; font-weight:700;">–</span>
						<div class="field" style="flex:1; margin:0;">
							<label for="r-max">{t('random.filters.max')}</label>
							<input id="r-max" class="text" type="number" bind:value={customMax} min="0" placeholder="∞" />
						</div>
					</div>
					{#if customMin || customMax}
						<p class="muted center" style="font-size:12px; margin-top:6px;">
							{customMin ? formatDuration(Number(customMin)) : '0'} – {customMax ? formatDuration(Number(customMax)) : t('random.filters.noLimit')}
						</p>
					{/if}
				</div>
			{/if}
		</div>

		{#if availableGenres.length > 0}
			<div class="flt-block">
				<p class="flt-label"><Icon name="sparkles" size={14} /> {t('random.filters.genre')}</p>
				<div class="chip-row">
					<button class="tab" class:active={selectedGenres.length === 0} onclick={() => selectedGenres = []}>{t('random.filters.anyGenre')}</button>
					{#each availableGenres as g}
						<button class="tab" class:active={selectedGenres.includes(g)} onclick={() => toggleGenre(g)}>{g}</button>
					{/each}
				</div>
			</div>
		{/if}

		{#if matchCount !== null}
			<p class="flt-count"><Icon name="list" size={14} /> <span>{tc('random.matchCount', matchCount)}</span></p>
		{/if}

		<!-- Desktop: botón grande -->
		<button class="btn btn-primary desk-only" style="width:100%; justify-content:center; font-size:15px; padding:15px; border-radius: var(--radius-sm); margin-top:22px;"
			onclick={roll} disabled={spinning}>
			{spinning ? t('random.searching') : t('random.rollDice')}
		</button>
	</div>

	<!-- ── Stage ── -->
	<div class="azar-stage roller-mode" class:has-result={hasResult}>
		{#if deckItems.length > 0}
			<RolodexRoller items={deckItems} targetId={pick?.id ?? null} spinToken={spinTokenCounter} onRoll={roll} onSettled={handleSettled} />
		{:else}
			<!-- Rolodex fantasma: mismos slivers y misma carta que el roller real,
			     para que antes de la primera tirada ya se vea qué va a pasar. -->
			<button class="roller-start" onclick={roll} disabled={spinning}>
				<span class="rs-sliver rs-far" aria-hidden="true"></span>
				<span class="rs-sliver rs-near" aria-hidden="true"></span>
				<span class="rs-card">
					<Icon name="sparkles" size={26} />
					<span>{spinning ? t('random.searching') : t('random.pressDice')}</span>
				</span>
				<span class="rs-sliver rs-near" aria-hidden="true"></span>
				<span class="rs-sliver rs-far" aria-hidden="true"></span>
			</button>
		{/if}
		<p class="dice-hint">
			{#if hasResult}<Icon name="refresh" size={14} /> {t('random.rollAgain')}{:else if spinning}{t('random.shuffling')}{/if}
		</p>

		<div class="result-slot">
			{#if error}
				<div class="stage-error">
					<p class="muted">😶 {error === t('errors.noPendingContent') ? t('random.noResultsInRange') : error}</p>
				</div>
			{:else if pick && !spinning}
				{@const item = pick}
				{@const landscape = ['youtube','game'].includes(item.content_type)}
				{@const link = buildConsumeUrl(pick)}
				<div class="result-inner reveal">
					<p class="result-kicker">
						{t('random.nextContent')}
						{#if tunedPick}<span class="tuned-tag"><Icon name="trendingUp" size={11} /> {t('random.attention.tuned')}</span>{/if}
					</p>
					<div class="c-card random-pick {landscape ? 'landscape' : 'portrait'}"
						style="--card-accent:{TYPE_COLOR[item.content_type]}; --accent:{TYPE_COLOR[item.content_type]}">
						{#if landscape}
							<div class="thumb-land">
								{#if item.thumbnail}<img src={item.thumbnail} alt="" />{:else}<div class="ph"><Icon name={TYPE_ICON[item.content_type]} size={40} /></div>{/if}
							</div>
						{:else}
							<div class="thumb-port">
								{#if item.thumbnail}<img src={item.thumbnail} alt="" />{:else}<div class="ph"><Icon name={TYPE_ICON[item.content_type]} size={40} /></div>{/if}
							</div>
						{/if}
						<div class="info">
							<div class="title" style="font-size:15px;">{item.title}</div>
							<div class="meta">
								<span class="badge">{typeLabel(item.content_type)}</span>
								{#if pickYear}<span class="pick-year">{pickYear}</span>{/if}
								{#if item.rating}<span class="pick-rating">★ {item.rating.toFixed(1)}</span>{/if}
								{#if item.content_type === 'series'}
									{#if item.seasons && item.seasons > 0}<span><Icon name="layers" size={13} /> {item.seasons}T</span>{/if}
									{#if item.episode_count && item.episode_count > 0}<span>{item.episode_count} ep</span>{/if}
									{#if item.duration_minutes > 0}<span><Icon name="clock" size={13} /> {formatDuration(item.duration_minutes)}/ep</span>{/if}
								{:else if item.duration_minutes > 0}
									<span><Icon name="clock" size={13} /> {formatDuration(item.duration_minutes)}</span>
								{/if}
								{#if item.author}<span>{item.author}</span>{/if}
							</div>
							<div class="actions" style="margin-top:10px;">
								{#if link}<a href={link} target="_blank" rel="noopener" onclick={() => markLaunched(item.id)}><button class="btn btn-primary"><Icon name="zap" size={14} /> {t('random.goNow')}</button></a>{/if}
								{#if pick?.trailer_url}<a href={pick.trailer_url} target="_blank" rel="noopener" onclick={() => markLaunched(item.id)}><button class="btn btn-trailer"><Icon name="play" size={14} /> {t('random.trailer')}</button></a>{/if}
								<button class="btn btn-consume" onclick={() => consume(pick!.id)}><Icon name="check" size={14} /> {t('random.done')}</button>
								<button class="btn" onclick={roll}><Icon name="refresh" size={14} /> {t('random.another')}</button>
							</div>
						</div>
					</div>

					<!-- Contexto para decidir sin abrir el detalle. Va fuera de la
					     ficha a propósito: dentro, la columna de info se queda en
					     175px en móvil y la sinopsis no se puede leer. -->
					{#if pickGenres.length || item.synopsis}
						<div class="pick-about">
							{#if pickGenres.length}
								<div class="pick-genres">
									{#each pickGenres.slice(0, 5) as g}<span class="pick-chip">{g}</span>{/each}
								</div>
							{/if}
							{#if item.synopsis}<p class="pick-synopsis">{item.synopsis}</p>{/if}
						</div>
					{/if}

					<p class="muted center retry">{t('random.notConvinced')} <button class="linkbtn" onclick={roll}>{t('random.tryAgain')}</button></p>
				</div>
			{:else if !spinning && deckItems.length === 0}
				<div class="random-empty desk-only">
					<div style="font-size:18px; font-weight:700;">{t('random.letFateDecide')}</div>
					<p class="muted" style="font-size:13px; max-width:320px; margin:0 auto;">{t('random.filterHint')}</p>
				</div>
			{/if}
		</div>
	</div>

	<!-- ── Tiempo de atención ──
	     Aparece cuando hay algo medido, es decir a partir de la segunda tirada:
	     el tiempo de un contenido se cierra justo cuando vuelves a tirar. -->
	{#if showAttention}
		<div class="attention-card">
			<div class="att-head">
				<p class="flt-label"><Icon name="activity" size={14} /> {t('random.attention.title')}</p>
				<button class="linkbtn att-reset" onclick={resetAttention}>{t('random.attention.reset')}</button>
			</div>
			<p class="att-hint">{t('random.attention.hint')}</p>

			<div class="att-items">
			<p class="att-sub">{t('random.attention.topItems')}</p>
			<ul class="att-list">
				{#each attentionTop as e (e.id)}
					{@const level = attentionLevel(e)}
					<li class="att-row" style="--tc:{TYPE_COLOR[e.type]}">
						<div class="att-thumb">
							{#if e.thumb}<img src={e.thumb} alt="" />{:else}<Icon name={TYPE_ICON[e.type] ?? 'list'} size={14} />{/if}
						</div>
						<div class="att-body">
							<div class="att-title">{e.title}</div>
							<div class="att-bar"><span style="width:{attentionMaxMs > 0 ? Math.max(6, Math.round((e.ms / attentionMaxMs) * 100)) : 0}%"></span></div>
						</div>
						<div class="att-meta">
							<span class="att-ms">{formatAttention(e.ms)}</span>
							<span class="att-level {level}">{t(`random.attention.level.${level}` as TKey)}</span>
						</div>
					</li>
				{/each}
			</ul>
			</div>

			<!-- Segunda columna en desktop ancho; en móvil sigue cayendo debajo -->
			<div class="att-affinity">
			{#if attentionTraits.length > 0}
				<p class="att-sub">{t('random.attention.affinity')}</p>
				<div class="att-traits">
					{#each attentionTraits as row (row.kind)}
						<div class="att-trait-row">
							<span class="att-kind">{t(`random.attention.kind.${row.kind}` as TKey)}</span>
							<div class="chip-row">
								{#each row.scores as s (s.value)}
									<span class="att-chip">{traitLabel(row.kind, s.value)} <b>{formatAttention(s.ms)}</b></span>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}

			<div class="att-actions">
				<button class="tab" class:active={attention.tuning} onclick={() => setTuning(!attention.tuning)}>
					<Icon name="trendingUp" size={13} /> {t('random.attention.tune')}
				</button>
				<button class="tab" onclick={applyAttentionFilters}>
					<Icon name="sparkles" size={13} /> {t('random.attention.applyFilters')}
				</button>
			</div>
			<p class="att-foot">
				{attention.tuning && !hasSignal() ? t('random.attention.needMore') : t('random.attention.tuneHint')}
				<br />{t('random.attention.local')}
			</p>
			</div>
		</div>
	{/if}
</div>
{/if}
