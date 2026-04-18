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

	// Game/YouTube: contain (no cropping). Everything else: cover.
	function thumbClass(type: ContentType): string {
		return type === 'game' || type === 'youtube' ? 'thumb thumb-contain' : 'thumb';
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
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}
<div class="random-page">
	<h1 class="random-title">
		<span>¿Qué consumo?</span>
	</h1>

	<!-- Type filter -->
	<div class="tabs" style="justify-content:center;">
		<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todo</button>
		<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
		<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬</button>
		<button class:btn-secondary={filter !== 'series'} onclick={() => filter = 'series'}>📺</button>
		<button class:btn-secondary={filter !== 'music'} onclick={() => filter = 'music'}>🎵</button>
		<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖</button>
		<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮</button>
	</div>

	<!-- Time filter -->
	<div class="time-section">
		<div class="time-label">⏱ ¿Cuánto tiempo tienes?</div>
		<div class="time-presets">
			{#each TIME_PRESETS as preset, i}
				<button
					class="time-btn"
					class:time-btn-active={!showCustom && selectedPreset === i}
					onclick={() => selectPreset(i)}
				>{preset.label}</button>
			{/each}
			<button
				class="time-btn"
				class:time-btn-active={showCustom}
				onclick={() => { showCustom = true; selectedPreset = -1; }}
			>⚙️ Exacto</button>
		</div>

		{#if showCustom}
			<div class="custom-range">
				<div class="custom-range-row">
					<div class="custom-field">
						<label for="r-min">Mín (min)</label>
						<input id="r-min" type="number" bind:value={customMin} min="0" placeholder="0" />
					</div>
					<span class="range-sep">–</span>
					<div class="custom-field">
						<label for="r-max">Máx (min)</label>
						<input id="r-max" type="number" bind:value={customMax} min="0" placeholder="∞" />
					</div>
				</div>
				{#if customMin || customMax}
					<p class="range-hint">
						{customMin ? formatDuration(Number(customMin)) : '0'}
						–
						{customMax ? formatDuration(Number(customMax)) : 'sin límite'}
					</p>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Roll button -->
	<button class="roll-btn" onclick={roll} disabled={spinning}>
		{spinning ? '🎲 Buscando…' : '🎲 Elegir al azar'}
	</button>

	{#if error}
		<div class="error-card">
			<p>😶 {error === 'No pending content in that time range'
				? 'Nada en ese rango de tiempo. Prueba con otro filtro.'
				: error}
			</p>
		</div>
	{/if}

	<!-- Result card -->
	{#if pick}
		{@const link = buildConsumeUrl(pick)}
		<div class="result-wrap">
			<div class="result-kicker">Tu siguiente contenido</div>
			<div class="content-card random-pick" style="--card-accent:var(--{pick.content_type})">
				{#if pick.thumbnail}
					<img class={thumbClass(pick.content_type)} src={pick.thumbnail} alt="" />
				{:else}
					<div class="{thumbClass(pick.content_type)} thumb-placeholder" style="font-size:2rem;">
						{TYPE_ICONS[pick.content_type] || '📄'}
					</div>
				{/if}
				<div class="info">
					<div class="title" style="font-size:1rem;">{pick.title}</div>
					<div class="meta">
						<span class="badge {pick.content_type}">{TYPE_LABELS[pick.content_type]}</span>
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
						<div class="series-total">~{formatDuration(pick.duration_minutes * pick.episode_count)} en total</div>
					{/if}
					<div class="actions" style="margin-top:0.6rem; flex-wrap:wrap;">
						{#if link}
							<a href={link} target="_blank" rel="noopener">
								<button>🚀 ¡Vamos!</button>
							</a>
						{/if}
						<button onclick={() => consume(pick!.id)} style="background:rgba(79,255,170,0.15); color:var(--game); box-shadow:none;">
							✓ Hecho
						</button>
						<button class="btn-secondary" onclick={roll}>🔄 Otro</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
{/if}

<style>
	.random-page {
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: 70dvh;
		text-align: center;
		gap: 1.25rem;
		padding-top: 0.5rem;
	}

	.random-title {
		font-size: 1.8rem;
		font-weight: 900;
		margin: 0;
	}
	.random-title span {
		background: linear-gradient(135deg, var(--primary), var(--game));
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	/* Time filter section */
	.time-section {
		width: 100%;
		max-width: 420px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}
	.time-label {
		font-size: 0.78rem;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.time-presets {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		justify-content: center;
	}
	.time-btn {
		background: var(--surface2);
		border: 1px solid var(--border);
		color: var(--text-muted);
		box-shadow: none;
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
		border-radius: 99px;
	}
	.time-btn:hover { background: var(--surface-hover); color: var(--text); box-shadow: none; }
	.time-btn-active {
		background: var(--primary-glow) !important;
		border-color: var(--primary) !important;
		color: var(--primary) !important;
		font-weight: 700;
	}

	/* Custom range */
	.custom-range {
		border-top: 1px solid var(--border);
		padding-top: 0.65rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.custom-range-row {
		display: flex;
		align-items: flex-end;
		gap: 0.5rem;
	}
	.custom-field {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		text-align: left;
	}
	.custom-field label { font-size: 0.72rem; color: var(--text-muted); }
	.custom-field input { font-size: 0.85rem; padding: 0.4rem 0.6rem; }
	.range-sep { color: var(--text-muted); padding-bottom: 0.5rem; font-weight: 700; }
	.range-hint { font-size: 0.75rem; color: var(--primary-dim); text-align: center; }

	/* Roll button */
	.roll-btn {
		font-size: 1.1rem;
		padding: 1rem 2.5rem;
		border-radius: 99px;
		min-width: 200px;
	}

	/* Error */
	.error-card {
		background: rgba(255,90,90,0.08);
		border: 1px solid rgba(255,90,90,0.2);
		border-radius: 12px;
		padding: 0.75rem 1.25rem;
		color: var(--danger);
		font-size: 0.9rem;
		max-width: 400px;
	}

	/* Result */
	.result-wrap {
		width: 100%;
		max-width: 480px;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		text-align: left;
	}
	.result-kicker {
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
		text-align: center;
	}

	/* Thumb placeholder reused */
	:global(.thumb-placeholder) {
		display: flex;
		align-items: center;
		justify-content: center;
	}
</style>
