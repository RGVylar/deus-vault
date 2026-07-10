<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, typeLabel, buildConsumeUrl } from '$lib/utils';
	import Icon from '$lib/components/Icon.svelte';
	import { t, tc, type TKey } from '$lib/i18n/index.svelte';
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
		youtube: 'play', movie: 'film', series: 'tv', music: 'music', book: 'book', game: 'game'
	};
	const TYPE_COLOR: Record<string, string> = {
		youtube: 'var(--youtube)', movie: 'var(--movie)', series: 'var(--series)',
		book: 'var(--book)', game: 'var(--game)', music: 'var(--music)'
	};
	const TYPES: { key: ContentType; icon: string }[] = [
		{ key: 'youtube', icon: 'play' }, { key: 'movie', icon: 'film' },
		{ key: 'series', icon: 'tv' },    { key: 'music', icon: 'music' },
		{ key: 'book', icon: 'book' },    { key: 'game', icon: 'game' },
	];

	// Caras del dado 3D (number = pips mostrados)
	const FACES = [
		{ t: 'translateZ(calc(var(--d) / 2))', n: 5 },
		{ t: 'rotateY(180deg) translateZ(calc(var(--d) / 2))', n: 2 },
		{ t: 'rotateY(90deg) translateZ(calc(var(--d) / 2))', n: 3 },
		{ t: 'rotateY(-90deg) translateZ(calc(var(--d) / 2))', n: 4 },
		{ t: 'rotateX(90deg) translateZ(calc(var(--d) / 2))', n: 6 },
		{ t: 'rotateX(-90deg) translateZ(calc(var(--d) / 2))', n: 1 },
	];
	const PIPS: Record<number, number[]> = { 1:[5], 2:[1,9], 3:[1,5,9], 4:[1,3,7,9], 5:[1,3,5,7,9], 6:[1,4,7,3,6,9] };

	let pick: Content | null = $state(null);
	let ghost: Content | null = $state(null);
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

	let cubeRot = $state({ rx: -22, ry: -28 });
	let recent: Content[] = [];

	const hasResult = $derived(!!pick || !!ghost || !!error);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		api.get<string[]>('/contents/genres').then(g => { availableGenres = g; }).catch(() => {});
	});

	function selectPreset(i: number) { selectedPreset = i; showCustom = false; customMin = ''; customMax = ''; }
	function toggleType(t: ContentType) { selectedTypes = selectedTypes.includes(t) ? selectedTypes.filter(x => x !== t) : [...selectedTypes, t]; }
	function toggleGenre(g: string) { selectedGenres = selectedGenres.includes(g) ? selectedGenres.filter(x => x !== g) : [...selectedGenres, g]; }

	function buildQuery(): string {
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
		const qs = params.toString();
		return qs ? '?' + qs : '';
	}

	$effect(() => {
		selectedTypes; selectedGenres; selectedPreset; showCustom; customMin; customMax;
		api.get<number>(`/contents/random/count${buildQuery()}`).then(n => matchCount = n).catch(() => matchCount = null);
	});

	async function roll() {
		if (spinning) return;
		error = '';
		spinning = true;
		cubeRot = { rx: cubeRot.rx - (720 + Math.floor(Math.random()*3)*360),
		            ry: cubeRot.ry + (720 + Math.floor(Math.random()*3)*360) };

		let flick = 0;
		const iv = recent.length ? setInterval(() => { ghost = recent[(flick++) % recent.length]; pick = null; }, 150) : null;

		const minWait = new Promise(r => setTimeout(r, 850));
		try {
			const fetched = await api.get<Content>(`/contents/random${buildQuery()}`);
			await minWait;
			if (iv) clearInterval(iv);
			ghost = null;
			pick = fetched;
			recent = [fetched, ...recent.filter(c => c.id !== fetched.id)].slice(0, 6);
		} catch (e: unknown) {
			if (iv) clearInterval(iv);
			ghost = null; pick = null;
			error = e instanceof Error ? e.message : t('errors.generic');
		} finally {
			spinning = false;
		}
	}

	async function consume(id: number) {
		await api.post(`/contents/${id}/consume`);
		pick = null; ghost = null;
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
		<button class="btn btn-primary desk-only" style="width:100%; justify-content:center; font-size:15px; padding:15px; border-radius:14px; margin-top:22px;"
			onclick={roll} disabled={spinning}>
			{spinning ? t('random.searching') : t('random.rollDice')}
		</button>
	</div>

	<!-- ── Stage ── -->
	<div class="azar-stage" class:has-result={hasResult}>
		<div class="dice-wrap" onclick={roll} role="button" tabindex="0">
			<div class="dice3d">
				<div class="cube" style="transform: rotateX({cubeRot.rx}deg) rotateY({cubeRot.ry}deg)">
					{#each FACES as f}
						<div class="face" style="transform:{f.t}">
							{#each Array(9) as _, i}
								<span>{#if PIPS[f.n].includes(i + 1)}<span class="pip"></span>{/if}</span>
							{/each}
						</div>
					{/each}
				</div>
			</div>
			<p class="dice-hint">
				{#if hasResult}<Icon name="refresh" size={14} /> {t('random.rollAgain')}{:else if spinning}{t('random.shuffling')}{:else}{t('random.pressDice')}{/if}
			</p>
		</div>

		<div class="result-slot">
			{#if error}
				<div class="stage-error">
					<p class="muted">😶 {error === t('errors.noPendingContent') ? t('random.noResultsInRange') : error}</p>
				</div>
			{:else if pick || ghost}
				{@const item = (pick ?? ghost)!}
				{@const isGhost = !pick}
				{@const landscape = ['youtube','movie','series','game'].includes(item.content_type)}
				{@const link = pick ? buildConsumeUrl(pick) : null}
				<div class="result-inner {isGhost ? 'ghost' : 'reveal'}">
					{#if !isGhost}<p class="result-kicker">{t('random.nextContent')}</p>{/if}
					<div class="c-card {isGhost ? '' : 'random-pick'} {landscape ? 'landscape' : 'portrait'}"
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
								{#if item.content_type === 'series'}
									{#if item.seasons && item.seasons > 0}<span><Icon name="layers" size={13} /> {item.seasons}T</span>{/if}
									{#if item.episode_count && item.episode_count > 0}<span>{item.episode_count} ep</span>{/if}
									{#if item.duration_minutes > 0}<span><Icon name="clock" size={13} /> {formatDuration(item.duration_minutes)}/ep</span>{/if}
								{:else if item.duration_minutes > 0}
									<span><Icon name="clock" size={13} /> {formatDuration(item.duration_minutes)}</span>
								{/if}
								{#if item.author}<span>{item.author}</span>{/if}
							</div>
							{#if !isGhost}
								<div class="actions" style="margin-top:10px;">
									{#if link}<a href={link} target="_blank" rel="noopener"><button class="btn btn-primary"><Icon name="zap" size={14} /> {t('random.goNow')}</button></a>{/if}
									{#if pick?.trailer_url}<a href={pick.trailer_url} target="_blank" rel="noopener"><button class="btn btn-trailer"><Icon name="play" size={14} /> {t('random.trailer')}</button></a>{/if}
									<button class="btn btn-consume" onclick={() => consume(pick!.id)}><Icon name="check" size={14} /> {t('random.done')}</button>
									<button class="btn" onclick={roll}><Icon name="refresh" size={14} /> {t('random.another')}</button>
								</div>
							{/if}
						</div>
					</div>
					{#if !isGhost}<p class="muted center retry">{t('random.notConvinced')} <button class="linkbtn" onclick={roll}>{t('random.tryAgain')}</button></p>{/if}
				</div>
			{:else}
				<div class="random-empty desk-only">
					<div style="font-size:18px; font-weight:700;">{t('random.letFateDecide')}</div>
					<p class="muted" style="font-size:13px; max-width:320px; margin:0 auto;">{t('random.filterHint')}</p>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}
