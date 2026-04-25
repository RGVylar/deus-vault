<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, ContentType } from '$lib/types';

	type TimePreset = { label: string; min: number | null; max: number | null };

	const TIME_PRESETS: TimePreset[] = [
		{ label: 'Cualquiera',    min: null, max: null  },
		{ label: '< 30 min',      min: null, max: 30    },
		{ label: '~1 hora',       min: 30,   max: 90    },
		{ label: '~2 horas',      min: 90,   max: 150   },
		{ label: 'Tarde libre',   min: 150,  max: null  },
	];

	// Portrait cards only (game anchors top)
	function thumbClass(type: ContentType): string {
		return type === 'game' ? 'thumb thumb-top' : 'thumb';
	}

	let pick: Content | null = $state(null);
	let filter: ContentType | 'all' = $state('all');
	let selectedPreset = $state(0); // index into TIME_PRESETS
	let showCustom = $state(false);
	let customMin = $state('');
	let customMax = $state('');
	let error = $state('');
	let spinning = $state(false);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
	});

	function activePreset(): TimePreset {
		return TIME_PRESETS[selectedPreset];
	}

	function selectPreset(i: number) {
		selectedPreset = i;
		showCustom = false;
		customMin = '';
		customMax = '';
	}

	async function roll() {
		error = '';
		spinning = true;
		try {
			const params = new URLSearchParams();
			if (filter !== 'all') params.set('content_type', filter);

			if (showCustom) {
				if (customMin) params.set('min_duration', String(Math.max(0, Number(customMin))));
				if (customMax) params.set('max_duration', String(Math.max(0, Number(customMax))));
			} else {
				const p = activePreset();
				if (p.min != null) params.set('min_duration', String(p.min));
				if (p.max != null) params.set('max_duration', String(p.max));
			}

			const qs = params.toString();
			pick = await api.get<Content>(`/contents/random${qs ? '?' + qs : ''}`);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Error';
			pick = null;
		} finally {
			spinning = false;
		}
	}

	async function consume(id: number) {
		await api.post(`/contents/${id}/consume`);
		pick = null;
	}

	// Label for active time filter
	const timeLabel = $derived(
		showCustom
			? (customMin || customMax
				? `${customMin ? customMin + ' min' : '0'} – ${customMax ? customMax + ' min' : '∞'}`
				: 'Rango personalizado')
			: TIME_PRESETS[selectedPreset].label
	);

	const TYPE_COLOR: Record<string, string> = {
		youtube: 'var(--youtube)',
		movie:   'var(--movie)',
		series:  'var(--series)',
		book:    'var(--book)',
		game:    'var(--game)',
		music:   'var(--music)',
	};
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">Redirigiendo…</p>
{:else}
<div class="roll-wrap">
	<div style="text-align:center;">
		<h1 style="margin-bottom:4px;">¿Qué consumo?</h1>
		<p class="muted" style="font-size:13px;">Deja que el azar decida</p>
	</div>

	<!-- Type filter -->
	<div class="tabs" style="justify-content:center;">
		<button class="tab" class:active={filter === 'all'} onclick={() => filter = 'all'}>Todo</button>
		<button class="tab" class:active={filter === 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
		<button class="tab" class:active={filter === 'movie'} onclick={() => filter = 'movie'}>🎬</button>
		<button class="tab" class:active={filter === 'series'} onclick={() => filter = 'series'}>📺</button>
		<button class="tab" class:active={filter === 'music'} onclick={() => filter = 'music'}>🎵</button>
		<button class="tab" class:active={filter === 'book'} onclick={() => filter = 'book'}>📖</button>
		<button class="tab" class:active={filter === 'game'} onclick={() => filter = 'game'}>🎮</button>
	</div>

	<!-- Dice button -->
	<button class="dice" class:spin={spinning} onclick={roll}>🎲</button>

	<!-- Time filter -->
	<div class="glass time-section">
		<div class="setting-group-title">⏱ ¿Cuánto tiempo tienes?</div>
		<div class="tabs" style="padding:4px 0 8px; justify-content:center;">
			{#each TIME_PRESETS as preset, i}
				<button
					class="tab"
					class:active={!showCustom && selectedPreset === i}
					onclick={() => selectPreset(i)}
				>{preset.label}</button>
			{/each}
			<button
				class="tab"
				class:active={showCustom}
				onclick={() => { showCustom = true; selectedPreset = -1; }}
			>⚙️ Exacto</button>
		</div>

		{#if showCustom}
			<div class="sep"></div>
			<div class="row" style="gap:12px; padding-top:8px;">
				<div class="field" style="flex:1;">
					<label for="r-min">Mín (min)</label>
					<input id="r-min" class="text" type="number" bind:value={customMin} min="0" placeholder="0" />
				</div>
				<span class="muted" style="padding-top:24px; font-weight:700;">–</span>
				<div class="field" style="flex:1;">
					<label for="r-max">Máx (min)</label>
					<input id="r-max" class="text" type="number" bind:value={customMax} min="0" placeholder="∞" />
				</div>
			</div>
			{#if customMin || customMax}
				<p class="muted center" style="font-size:12px; margin-top:4px;">
					{customMin ? formatDuration(Number(customMin)) : '0'}
					–
					{customMax ? formatDuration(Number(customMax)) : 'sin límite'}
				</p>
			{/if}
		{/if}
	</div>

	{#if error}
		<div class="glass" style="padding:12px 16px; border-color:color-mix(in oklab, var(--danger) 30%, transparent);">
			<p class="muted center">😶 {error === 'No pending content in that time range'
				? 'Nada en ese rango de tiempo. Prueba con otro filtro.'
				: error}
			</p>
		</div>
	{/if}

	<!-- Result card -->
	{#if pick}
		{@const link = buildConsumeUrl(pick)}
		{@const landscape = pick.content_type === 'youtube' || pick.content_type === 'movie' || pick.content_type === 'series' || pick.content_type === 'game'}
		<div style="width:100%;">
			<p class="muted center" style="font-size:10px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:8px;">Tu siguiente contenido</p>
			<div
				class="c-card random-pick"
				class:landscape
				class:portrait={!landscape}
				style="--card-accent:{TYPE_COLOR[pick.content_type] ?? 'var(--primary)'}; --accent:{TYPE_COLOR[pick.content_type] ?? 'var(--primary)'}"
			>
				{#if landscape}
					<div class="thumb-land">
						{#if pick.thumbnail}
							<img src={pick.thumbnail} alt="" />
						{:else}
							<div class="ph">{TYPE_ICONS[pick.content_type] || '📄'}</div>
						{/if}
					</div>
				{:else}
					<div class="thumb-port">
						{#if pick.thumbnail}
							<img src={pick.thumbnail} alt="" />
						{:else}
							<div class="ph">{TYPE_ICONS[pick.content_type] || '📄'}</div>
						{/if}
					</div>
				{/if}
				<div class="info">
					<div class="title" style="font-size:15px;">{pick.title}</div>
					<div class="meta">
						<span class="badge">{TYPE_LABELS[pick.content_type]}</span>
						{#if pick.content_type === 'series'}
							{#if pick.seasons && pick.seasons > 0}<span>📺 {pick.seasons}T</span>{/if}
							{#if pick.episode_count && pick.episode_count > 0}<span>{pick.episode_count} ep</span>{/if}
							{#if pick.duration_minutes > 0}<span>⏱ {formatDuration(pick.duration_minutes)}/ep</span>{/if}
						{:else if pick.duration_minutes > 0}
							<span>⏱ {formatDuration(pick.duration_minutes)}</span>
						{/if}
						{#if pick.author}<span>{pick.author}</span>{/if}
					</div>
					{#if pick.content_type === 'series' && pick.episode_count && pick.episode_count > 0 && pick.duration_minutes > 0}
						<div style="font-size:11px; font-weight:600; color:var(--series);">~{formatDuration(pick.duration_minutes * pick.episode_count)} en total</div>
					{/if}
					<div class="actions" style="margin-top:10px;">
						{#if link}
							<a href={link} target="_blank" rel="noopener">
								<button class="btn btn-primary">🚀 ¡Vamos!</button>
							</a>
						{/if}
						<button class="btn btn-consume" onclick={() => consume(pick!.id)}>✓ Hecho</button>
						<button class="btn" onclick={roll}>🔄 Otro</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
{/if}

<style>
	.time-section {
		width: 100%;
		padding: 14px 16px;
		border-radius: 18px;
	}
</style>
