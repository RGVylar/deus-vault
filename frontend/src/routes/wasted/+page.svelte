<script lang="ts">
	import { onMount } from 'svelte';
	import { distractionsApi } from '$lib/api';
	import { t, tc } from '$lib/i18n/index.svelte';
	import type { DistractionStats } from '$lib/types';

	let stats = $state<DistractionStats | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const PLATFORM_META: Record<string, { label: string; icon: string; color: string }> = {
		shorts:  { label: 'YouTube Shorts',  icon: '📱', color: 'oklch(0.65 0.22 25)'  },
		tiktok:  { label: 'TikTok',          icon: '🎵', color: 'oklch(0.75 0.15 190)' },
		twitter: { label: 'Twitter / X',     icon: '🐦', color: 'oklch(0.70 0.14 240)' },
		reels:   { label: 'Instagram Reels', icon: '📸', color: 'oklch(0.70 0.20 340)' }
	};

	function meta(platform: string) {
		return PLATFORM_META[platform] ?? { label: platform, icon: '🕳️', color: 'var(--primary)' };
	}

	function fmtDur(seconds: number): string {
		const mins = Math.round(seconds / 60);
		if (mins < 1) return seconds > 0 ? '<1m' : '0m';
		if (mins < 60) return `${mins}m`;
		const h = Math.floor(mins / 60);
		const m = mins % 60;
		return m > 0 ? `${h}h ${m}m` : `${h}h`;
	}

	function fmtMins(mins: number): string {
		return fmtDur(mins * 60);
	}

	// Daily totals for the bar chart (last 30 days, filling gaps)
	let dailyTotals = $derived.by(() => {
		if (!stats) return [];
		const byDate = new Map<string, number>();
		for (const d of stats.days) {
			byDate.set(d.date, (byDate.get(d.date) ?? 0) + d.seconds);
		}
		const out: { date: string; seconds: number; label: string }[] = [];
		const today = new Date();
		for (let i = 29; i >= 0; i--) {
			const d = new Date(today);
			d.setDate(today.getDate() - i);
			const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
			out.push({
				date: key,
				seconds: byDate.get(key) ?? 0,
				label: `${d.getDate()}/${d.getMonth() + 1}`
			});
		}
		return out;
	});

	let platformTotalSeconds = $derived(
		Math.max(1, (stats?.platforms ?? []).reduce((acc, p) => acc + p.seconds, 0))
	);

	// Bueno por día (segundos), para las comparativas
	let goodByDate = $derived.by(() => {
		const m = new Map<string, number>();
		for (const g of stats?.good_days ?? []) m.set(g.date, g.minutes * 60);
		return m;
	});

	let dailyPairs = $derived(
		dailyTotals.map((d) => ({ ...d, goodSeconds: goodByDate.get(d.date) ?? 0 }))
	);

	let maxPairSecs = $derived(
		Math.max(1, ...dailyPairs.map((d) => Math.max(d.seconds, d.goodSeconds)))
	);

	// Ratio señal/ruido por periodo
	// Con muy poca actividad acumulada el ratio se dispara a 100% (o 0%) con datos
	// insignificantes -p. ej. "Hoy" en cuanto se marca un solo vídeo bueno-, así que
	// exigimos un mínimo de señal antes de mostrar un porcentaje real.
	const MIN_MEANINGFUL_SECONDS = 5 * 60;
	let periods = $derived.by(() => {
		if (!stats) return [];
		const mk = (label: string, goodMins: number, badSecs: number) => {
			const good = goodMins * 60;
			const total = good + badSecs;
			return { label, good, bad: badSecs, ratio: total >= MIN_MEANINGFUL_SECONDS ? good / total : null };
		};
		return [
			mk(t('wasted.today'), stats.good_today_minutes, stats.today_seconds),
			mk(t('wasted.period7days'), stats.good_week_minutes, stats.week_seconds),
			mk(t('wasted.period30days'), stats.good_month_minutes, stats.month_seconds),
			mk(t('wasted.periodTotal'), stats.good_total_minutes, stats.total_seconds)
		];
	});

	// Por día de la semana (suma de los últimos 30 días)
	// Las abreviaturas traducidas se repiten en varios idiomas (en: M T W T F S S;
	// pt: S T Q Q S S D), así que el {#each} se keyea por `id`, no por `label`.
	const WEEKDAY_IDS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
	let weekdayData = $derived.by(() => {
		const bad = Array(7).fill(0);
		const good = Array(7).fill(0);
		for (const d of dailyPairs) {
			const dow = (new Date(d.date + 'T12:00:00').getDay() + 6) % 7; // lunes = 0
			bad[dow] += d.seconds;
			good[dow] += d.goodSeconds;
		}
		return WEEKDAY_IDS.map((id, i) => ({
			id,
			label: t(`wasted.weekday.${id}`),
			bad: bad[i],
			good: good[i]
		}));
	});

	let maxWeekday = $derived(
		Math.max(1, ...weekdayData.map((w) => Math.max(w.bad, w.good)))
	);

	async function load() {
		loading = true;
		error = null;
		try {
			stats = await distractionsApi.stats(30);
		} catch (e: any) {
			error = e.message ?? t('wasted.loadError');
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="page">
	<h1 class="page-title">{t('wasted.title')}</h1>

	{#if error}
		<div class="error-banner">{error} <button onclick={() => (error = null)}>×</button></div>
	{/if}

	{#if loading}
		<div class="empty-state">{t('wasted.loading')}</div>
	{:else if stats}
		<!-- Hero + side panel -->
		<div class="top-grid">
			<div class="hero-card">
				<div class="hero-label">{t('wasted.lostTime')}</div>
				<div class="hero-value">{fmtDur(stats.total_seconds)}</div>
				<div class="hero-caption">
					{t('wasted.lostForeverPrefix', { time: fmtDur(stats.total_seconds) })}{#if stats.total_items > 0}
						{' '}{tc('wasted.trashVideoCount', stats.total_items)}{/if}
				</div>
				<div class="hero-vs">
					vs <strong>{fmtMins(stats.good_total_minutes)}</strong> {t('wasted.vsGoodContent')}
				</div>

				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-label">{t('wasted.today')}</div>
						<div class="stat-value">{fmtDur(stats.today_seconds)}</div>
						<div class="stat-sub">{t('wasted.vsGood', { mins: fmtMins(stats.good_today_minutes) })}</div>
					</div>
					<div class="stat-card">
						<div class="stat-label">{t('wasted.last7days')}</div>
						<div class="stat-value">{fmtDur(stats.week_seconds)}</div>
						<div class="stat-sub">{t('wasted.vsGood', { mins: fmtMins(stats.good_week_minutes) })}</div>
					</div>
					<div class="stat-card">
						<div class="stat-label">{t('wasted.last30days')}</div>
						<div class="stat-value">{fmtDur(stats.month_seconds)}</div>
						<div class="stat-sub">{t('wasted.vsGood', { mins: fmtMins(stats.good_month_minutes) })}</div>
					</div>
				</div>
			</div>

			<aside class="side-card">
				<div class="side-title">{t('wasted.leakSource')}</div>
				{#if stats.platforms.length === 0}
					<div class="side-empty">{t('wasted.noLeaksYet')}</div>
				{:else}
					<div class="platform-list">
						{#each stats.platforms as p (p.platform)}
							<div class="platform-row">
								<span class="platform-ico">{meta(p.platform).icon}</span>
								<div class="platform-info">
									<div class="platform-head">
										<span class="platform-name">{meta(p.platform).label}</span>
										<span class="platform-time">
											{fmtDur(p.seconds)}
											{#if p.items_count > 0}
												{tc('wasted.videosCount', p.items_count)}
											{/if}
										</span>
									</div>
									<div class="platform-track">
										<div
											class="platform-fill"
											style="width:{(p.seconds / platformTotalSeconds) * 100}%; background:{meta(p.platform).color}"
										></div>
									</div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</aside>
		</div>

		{#if stats.total_seconds === 0}
			<div class="empty-state">
				<div class="empty-icon">🕳️</div>
				{t('wasted.nothingLostYet')}
			</div>
		{:else}
			<div class="mid-grid">
				<!-- Señal vs ruido por periodo -->
				<section class="panel">
					<h2 class="panel-title">{t('wasted.signalVsNoise')} <span class="panel-sub">{t('wasted.pctWellSpent')}</span></h2>
					<div class="period-list">
						{#each periods as p (p.label)}
							<div class="period-row">
								<span class="period-label">{p.label}</span>
								<div
									class="period-track"
									class:empty={p.ratio === null}
									title="{p.label}: {fmtDur(p.good)} {t('wasted.good')} vs {fmtDur(p.bad)} {t('wasted.trash')}"
								>
									{#if p.ratio !== null}
										<div class="period-good" style="width:{p.ratio * 100}%"></div>
									{/if}
								</div>
								<span class="period-pct">{p.ratio === null ? '—' : `${Math.round(p.ratio * 100)}%`}</span>
							</div>
						{/each}
					</div>
					<div class="legend">
						<span class="dot good"></span> {t('wasted.goodContent')}
						<span class="dot bad-dot"></span> {t('wasted.trash')}
					</div>
				</section>

				<!-- Por día de la semana -->
				<section class="panel">
					<h2 class="panel-title">{t('wasted.byWeekday')} <span class="panel-sub">{t('wasted.last30daysLower')}</span></h2>
					<div class="wchart">
						{#each weekdayData as w (w.id)}
							<div class="wcol" title="{w.label}: {fmtDur(w.good)} {t('wasted.good')} · {fmtDur(w.bad)} {t('wasted.trash')}">
								<div class="wbars">
									<div class="wbar good" style="height:{Math.max(w.good > 0 ? 3 : 1, (w.good / maxWeekday) * 100)}%"></div>
									<div class="wbar bad"  style="height:{Math.max(w.bad  > 0 ? 3 : 1, (w.bad  / maxWeekday) * 100)}%"></div>
								</div>
								<div class="wlabel">{w.label}</div>
							</div>
						{/each}
					</div>
					<div class="legend">
						<span class="dot good"></span> {t('wasted.good')}
						<span class="dot bad-dot"></span> {t('wasted.trash')}
					</div>
				</section>
			</div>

			<!-- Bueno vs basura, últimos 30 días -->
			<section class="panel">
				<h2 class="panel-title">
					{t('wasted.goodVsTrash')} <span class="panel-sub">{t('wasted.goodVsTrashSub')}</span>
				</h2>
				<div class="dchart">
					{#each dailyPairs as day (day.date)}
						<div
							class="dcol"
							title="{day.label} · {t('wasted.good')}: {fmtDur(day.goodSeconds)} · {t('wasted.trash')}: {fmtDur(day.seconds)}"
						>
							<div class="dcol-top">
								<div
									class="dbar good"
									style="height:{Math.max(day.goodSeconds > 0 ? 3 : 0, (day.goodSeconds / maxPairSecs) * 100)}%"
								></div>
							</div>
							<div class="dcol-bottom">
								<div
									class="dbar bad"
									style="height:{Math.max(day.seconds > 0 ? 3 : 0, (day.seconds / maxPairSecs) * 100)}%"
								></div>
							</div>
						</div>
					{/each}
				</div>
				<div class="chart-labels">
					<span>{dailyPairs[0]?.label}</span>
					<span>{t('wasted.todayLower')}</span>
				</div>
			</section>
		{/if}
	{/if}
</div>

<style>
	.page {
		padding: 24px 28px 90px;
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.page-title {
		font-size: 30px;
		font-weight: 800;
		color: var(--text);
		line-height: 1.1;
	}

	/* ── Top grid: hero + side panel ─────────────────────────── */

	.top-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 18px;
	}

	@media (min-width: 980px) {
		.top-grid {
			grid-template-columns: 2fr 1fr;
		}
	}

	.hero-card,
	.side-card,
	.panel {
		background: var(--glass-bg);
		backdrop-filter: blur(16px);
		-webkit-backdrop-filter: blur(16px);
		border: 1px solid var(--glass-border);
		border-radius: 20px;
	}

	.hero-card {
		padding: 28px 32px;
		display: flex;
		flex-direction: column;
	}

	.hero-label {
		font-size: 12px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.22em;
		color: var(--text-dim);
	}

	.hero-value {
		margin-top: 8px;
		font-size: clamp(64px, 8vw, 112px);
		font-weight: 900;
		line-height: 1;
		letter-spacing: -0.03em;
		background: linear-gradient(120deg, oklch(0.72 0.21 25), oklch(0.65 0.26 355));
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		filter: drop-shadow(0 0 28px oklch(0.6 0.22 25 / 0.3));
	}

	.hero-caption {
		margin-top: 10px;
		font-size: 14px;
		color: var(--text-muted);
	}

	.hero-vs {
		margin-top: 2px;
		font-size: 14px;
		color: var(--text-muted);
	}

	.hero-vs strong {
		color: oklch(0.72 0.17 150);
		font-weight: 700;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
		margin-top: 22px;
	}

	.stat-card {
		background: oklch(0.2 0.03 300 / 0.35);
		border: 1px solid var(--glass-border);
		border-radius: 14px;
		padding: 12px 14px;
	}

	.stat-label {
		font-size: 11px;
		color: var(--text-dim);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.stat-value {
		font-size: 22px;
		font-weight: 800;
		color: oklch(0.68 0.2 25);
		margin-top: 2px;
	}

	.stat-sub {
		font-size: 12px;
		color: var(--text-muted);
		margin-top: 2px;
	}

	/* ── Side panel ──────────────────────────────────────────── */

	.side-card {
		padding: 22px 24px;
	}

	.side-title {
		font-size: 12px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.22em;
		color: var(--text-dim);
		margin-bottom: 18px;
	}

	.side-empty {
		font-size: 13px;
		color: var(--text-muted);
	}

	.platform-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.platform-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.platform-ico {
		font-size: 20px;
		width: 28px;
		text-align: center;
	}

	.platform-info {
		flex: 1;
		min-width: 0;
	}

	.platform-head {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		font-size: 13px;
		margin-bottom: 4px;
	}

	.platform-name {
		color: var(--text);
		font-weight: 600;
	}

	.platform-time {
		color: var(--text-muted);
		white-space: nowrap;
	}

	.platform-track {
		height: 6px;
		border-radius: 999px;
		background: var(--glass-border);
		overflow: hidden;
	}

	.platform-fill {
		height: 100%;
		border-radius: 999px;
		transition: width 0.5s ease;
	}

	/* ── Panels ──────────────────────────────────────────────── */

	.panel {
		padding: 20px 24px;
	}

	.panel-title {
		font-size: 15px;
		font-weight: 700;
		color: var(--text);
		margin-bottom: 14px;
	}

	.panel-sub {
		font-size: 12px;
		font-weight: 500;
		color: var(--text-dim);
	}

	/* Grid intermedio: dos paneles comparativos */
	.mid-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 18px;
	}

	@media (min-width: 980px) {
		.mid-grid {
			grid-template-columns: 1fr 1fr;
		}
	}

	/* Señal vs ruido por periodo */
	.period-list {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.period-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.period-label {
		width: 56px;
		flex-shrink: 0;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-muted);
		text-align: right;
	}

	.period-track {
		flex: 1;
		height: 14px;
		border-radius: 999px;
		overflow: hidden;
		background: oklch(0.55 0.18 25 / 0.55);
	}

	.period-track.empty {
		background: var(--glass-border);
	}

	.period-good {
		height: 100%;
		background: oklch(0.72 0.17 150);
		transition: width 0.5s ease;
	}

	.period-pct {
		width: 44px;
		flex-shrink: 0;
		font-size: 13px;
		font-weight: 700;
		color: var(--text);
		text-align: right;
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 6px 12px;
		margin-top: 14px;
		font-size: 12px;
		color: var(--text-muted);
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		display: inline-block;
	}

	.dot.good {
		background: oklch(0.72 0.17 150);
	}

	.dot.bad-dot {
		background: oklch(0.62 0.19 25);
	}

	/* Por día de la semana */
	.wchart {
		display: flex;
		align-items: flex-end;
		gap: 10px;
		height: 130px;
	}

	.wcol {
		flex: 1;
		height: 100%;
		display: flex;
		flex-direction: column;
	}

	.wbars {
		flex: 1;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		gap: 3px;
	}

	.wbar {
		width: 100%;
		max-width: 26px;
		border-radius: 4px 4px 0 0;
		min-height: 1px;
	}

	.wbar.good {
		background: oklch(0.72 0.17 150 / 0.9);
	}

	.wbar.bad {
		background: oklch(0.62 0.19 25 / 0.9);
	}

	.wlabel {
		text-align: center;
		margin-top: 6px;
		font-size: 11px;
		color: var(--text-dim);
	}

	/* Gráfica divergente bueno/basura */
	.dchart {
		display: flex;
		gap: 4px;
		height: 200px;
	}

	.dcol {
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.dcol-top {
		flex: 1;
		display: flex;
		align-items: flex-end;
	}

	.dcol-bottom {
		flex: 1;
		display: flex;
		align-items: flex-start;
		border-top: 1px solid var(--glass-border);
	}

	.dbar {
		width: 100%;
	}

	.dbar.good {
		background: oklch(0.72 0.17 150 / 0.9);
		border-radius: 3px 3px 0 0;
	}

	.dbar.bad {
		background: oklch(0.62 0.19 25 / 0.9);
		border-radius: 0 0 3px 3px;
	}

	.chart-labels {
		display: flex;
		justify-content: space-between;
		margin-top: 6px;
		font-size: 11px;
		color: var(--text-dim);
	}

	/* ── Misc ────────────────────────────────────────────────── */

	.error-banner {
		padding: 10px 14px;
		border-radius: 12px;
		background: oklch(0.3 0.1 25 / 0.5);
		border: 1px solid oklch(0.5 0.15 25 / 0.5);
		color: var(--text);
		font-size: 13px;
		display: flex;
		justify-content: space-between;
	}

	.empty-state {
		padding: 60px 24px;
		text-align: center;
		color: var(--text-muted);
		font-size: 14px;
		line-height: 1.6;
		max-width: 420px;
		margin: 0 auto;
	}

	.empty-icon {
		font-size: 40px;
		margin-bottom: 10px;
	}

	@media (max-width: 640px) {
		.page {
			padding: 20px 16px 90px;
		}
		.stats-row {
			grid-template-columns: 1fr;
		}
		.hero-card {
			padding: 22px 20px;
		}
	}
</style>
