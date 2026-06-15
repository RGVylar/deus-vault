<!--
  REFERENCIA · frontend/src/routes/random/+page.svelte (rediseñado)
  ----------------------------------------------------------------
  Svelte 5 (runes). Conserva TODA la lógica del archivo actual:
  api.get('/contents/random'), géneros, consume, TIME_PRESETS, custom range.
  Cambios: markup nuevo (dado 3D + stage + reveal), iconos vía <Icon>,
  estado `spinning` con tumble del dado y flicker de "barajado".

  Renómbralo a +page.svelte al portarlo. Requiere el CSS de azar.css
  añadido a app.css.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import Icon from '$lib/components/Icon.svelte';
	import type { Content, ContentType } from '$lib/types';

	type TimePreset = { label: string; min: number | null; max: number | null };
	const TIME_PRESETS: TimePreset[] = [
		{ label: 'Cualquiera',  min: null, max: null },
		{ label: '< 30 min',    min: null, max: 30   },
		{ label: '~1 hora',     min: 30,   max: 90   },
		{ label: '~2 horas',    min: 90,   max: 150  },
		{ label: 'Tarde libre', min: 150,  max: null },
	];

	// Tipo → nombre de icono en Icon.svelte (ver README: youtube usa "play")
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
	let ghost: Content | null = $state(null);   // carta de "barajado"
	let filter: ContentType | 'all' = $state('all');
	let selectedPreset = $state(0);
	let showCustom = $state(false);
	let customMin = $state('');
	let customMax = $state('');
	let selectedGenre = $state('');
	let availableGenres = $state<string[]>([]);
	let error = $state('');
	let spinning = $state(false);

	let cubeRot = $state({ rx: -22, ry: -28 });
	let recent: Content[] = [];   // cache para el flicker de barajado

	const hasResult = $derived(!!pick || !!ghost || !!error);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		api.get<string[]>('/contents/genres').then(g => { availableGenres = g; }).catch(() => {});
	});

	function selectPreset(i: number) { selectedPreset = i; showCustom = false; customMin = ''; customMax = ''; }

	function buildQuery(): string {
		const params = new URLSearchParams();
		if (filter !== 'all') params.set('content_type', filter);
		if (showCustom) {
			if (customMin) params.set('min_duration', String(Math.max(0, Number(customMin))));
			if (customMax) params.set('max_duration', String(Math.max(0, Number(customMax))));
		} else {
			const p = TIME_PRESETS[selectedPreset];
			if (p.min != null) params.set('min_duration', String(p.min));
			if (p.max != null) params.set('max_duration', String(p.max));
		}
		if (selectedGenre) params.set('genre', selectedGenre);
		const qs = params.toString();
		return qs ? '?' + qs : '';
	}

	async function roll() {
		if (spinning) return;
		error = '';
		spinning = true;
		// 1) tumble del dado (vuelve siempre a la misma pose 3D — múltiplos de 360)
		cubeRot = { rx: cubeRot.rx - (720 + Math.floor(Math.random()*3)*360),
		            ry: cubeRot.ry + (720 + Math.floor(Math.random()*3)*360) };

		// 2) flicker de "barajado" con picks recientes (si hay), mientras se resuelve la petición
		let flick = 0;
		const iv = recent.length ? setInterval(() => { ghost = recent[(flick++) % recent.length]; pick = null; }, 150) : null;

		// 3) petición real + mínimo 850ms de suspense
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
			error = e instanceof Error ? e.message : 'Error';
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
	<p class="muted center">Redirigiendo…</p>
{:else}

<!-- Desktop topbar -->
<div class="desk-topbar desk-only">
	<h1 class="desk-title">¿Qué consumo?</h1>
	<div class="desk-spacer"></div>
</div>

<div class="azar">

	<!-- Título móvil -->
	<div class="azar-head">
		<h1>¿Qué consumo?</h1>
		<p>Deja que el azar decida</p>
	</div>

	<!-- ── Filtros ── -->
	<div class="azar-filters">
		<div class="flt-block">
			<p class="flt-label"><Icon name="layers" size={14} /> Tipo</p>
			<div class="type-row">
				<button class="type-btn all" class:active={filter === 'all'} onclick={() => filter = 'all'}>Todo</button>
				{#each TYPES as t}
					<button class="type-btn" class:active={filter === t.key}
						style="--tc:{TYPE_COLOR[t.key]}" onclick={() => filter = t.key} aria-label={TYPE_LABELS[t.key]}>
						<Icon name={t.icon} size={21} />
					</button>
				{/each}
			</div>
		</div>

		<div class="flt-block">
			<p class="flt-label"><Icon name="clock" size={14} /> Tiempo disponible</p>
			<div class="chip-row">
				{#each TIME_PRESETS as preset, i}
					<button class="tab" class:active={!showCustom && selectedPreset === i} onclick={() => selectPreset(i)}>{preset.label}</button>
				{/each}
				<button class="tab" class:active={showCustom} onclick={() => { showCustom = true; selectedPreset = -1; }}>Exacto</button>
			</div>
			{#if showCustom}
				<div class="custom-range show">
					<div class="row">
						<div class="field" style="flex:1; margin:0;">
							<label for="r-min">Mín (min)</label>
							<input id="r-min" class="text" type="number" bind:value={customMin} min="0" placeholder="0" />
						</div>
						<span class="muted" style="padding-top:24px; font-weight:700;">–</span>
						<div class="field" style="flex:1; margin:0;">
							<label for="r-max">Máx (min)</label>
							<input id="r-max" class="text" type="number" bind:value={customMax} min="0" placeholder="∞" />
						</div>
					</div>
					{#if customMin || customMax}
						<p class="muted center" style="font-size:12px; margin-top:6px;">
							{customMin ? formatDuration(Number(customMin)) : '0'} – {customMax ? formatDuration(Number(customMax)) : 'sin límite'}
						</p>
					{/if}
				</div>
			{/if}
		</div>

		{#if availableGenres.length > 0}
			<div class="flt-block">
				<p class="flt-label"><Icon name="sparkles" size={14} /> Género</p>
				<select class="text" bind:value={selectedGenre}>
					<option value="">Cualquiera</option>
					{#each availableGenres as g}<option value={g}>{g}</option>{/each}
				</select>
			</div>
		{/if}

		<!-- Desktop: botón grande -->
		<button class="btn btn-primary desk-only" style="width:100%; justify-content:center; font-size:15px; padding:15px; border-radius:14px; margin-top:22px;"
			onclick={roll} disabled={spinning}>
			{spinning ? 'Buscando…' : 'Tirar el dado'}
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
				{#if hasResult}<Icon name="refresh" size={14} /> Tirar de nuevo{:else if spinning}Barajando…{:else}Pulsa el dado{/if}
			</p>
		</div>

		<div class="result-slot">
			{#if error}
				<div class="stage-error">
					<p class="muted">😶 {error === 'No pending content in that time range' ? 'Nada en ese rango. Prueba con otro filtro.' : error}</p>
				</div>
			{:else if pick || ghost}
				{@const item = (pick ?? ghost)!}
				{@const isGhost = !pick}
				{@const landscape = ['youtube','movie','series','game'].includes(item.content_type)}
				{@const link = pick ? buildConsumeUrl(pick) : null}
				<div class="result-inner {isGhost ? 'ghost' : 'reveal'}">
					{#if !isGhost}<p class="result-kicker">Tu siguiente contenido</p>{/if}
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
								<span class="badge">{TYPE_LABELS[item.content_type]}</span>
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
									{#if link}<a href={link} target="_blank" rel="noopener"><button class="btn btn-primary"><Icon name="zap" size={14} /> ¡Vamos!</button></a>{/if}
									{#if pick?.trailer_url}<a href={pick.trailer_url} target="_blank" rel="noopener"><button class="btn btn-trailer"><Icon name="play" size={14} /> Trailer</button></a>{/if}
									<button class="btn btn-consume" onclick={() => consume(pick!.id)}><Icon name="check" size={14} /> Hecho</button>
									<button class="btn" onclick={roll}><Icon name="refresh" size={14} /> Otro</button>
								</div>
							{/if}
						</div>
					</div>
					{#if !isGhost}<p class="muted center retry">¿No te convence? <button class="linkbtn" onclick={roll}>Tira de nuevo</button></p>{/if}
				</div>
			{:else}
				<!-- Sin resultado aún: en desktop puede mostrarse un texto tenue; en móvil se oculta -->
				<div class="random-empty desk-only">
					<div style="font-size:18px; font-weight:700;">Que el azar decida</div>
					<p class="muted" style="font-size:13px; max-width:320px; margin:0 auto;">Filtra por tipo y tiempo disponible, y pulsa el dado.</p>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}
