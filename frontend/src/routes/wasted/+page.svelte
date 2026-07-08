<script lang="ts">
	import { onMount } from 'svelte';
	import { distractionsApi } from '$lib/api';
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

	let maxDaily = $derived(Math.max(1, ...dailyTotals.map((d) => d.seconds)));
	let platformTotalSeconds = $derived(
		Math.max(1, (stats?.platforms ?? []).reduce((acc, p) => acc + p.seconds, 0))
	);

	// Ratio señal/ruido de la semana
	let weekGoodSecs = $derived((stats?.good_week_minutes ?? 0) * 60);
	let weekBadSecs = $derived(stats?.week_seconds ?? 0);
	let weekRatio = $derived.by(() => {
		const total = weekGoodSecs + weekBadSecs;
		return total > 0 ? weekGoodSecs / total : null;
	});

	async function load() {
		loading = true;
		error = null;
		try {
			stats = await distractionsApi.stats(30);
		} catch (e: any) {
			error = e.message ?? 'Error al cargar';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="page">
	<div class="page-header">
		<div class="page-header-top">
			<div>
				<h1 class="page-title">Bóveda de lo Perdido</h1>
				<p class="page-sub">Tiempo que no volverá</p>
			</div>
		</div>

		{#if stats}
			<div class="total-hero">
				<div class="total-value">{fmtDur(stats.total_seconds)}</div>
				<div class="total-caption">
					perdidas para siempre{#if stats.total_items > 0}&nbsp;· {stats.total_items} vídeos basura{/if}
				</div>
				<div class="total-vs">
					vs <strong>{fmtMins(stats.good_total_minutes)}</strong> de contenido bueno en total
				</div>
			</div>
		{/if}

		{#if stats}
			<div class="stats-row">
				<div class="stat-card">
					<div class="stat-label">Hoy</div>
					<div class="stat-value bad">{fmtDur(stats.today_seconds)}</div>
					<div class="stat-sub">vs {fmtMins(stats.good_today_minutes)} de bueno</div>
				</div>
				<div class="stat-card">
					<div class="stat-label">Últimos 7 días</div>
					<div class="stat-value bad">{fmtDur(stats.week_seconds)}</div>
					<div class="stat-sub">vs {fmtMins(stats.good_week_minutes)} de bueno</div>
				</div>
				<div class="stat-card">
					<div class="stat-label">Últimos 30 días</div>
					<div class="stat-value bad">{fmtDur(stats.month_seconds)}</div>
					<div class="stat-sub">vs {fmtMins(stats.good_month_minutes)} de bueno</div>
				</div>
			</div>
		{/if}
	</div>

	{#if error}
		<div class="error-banner">{error} <button onclick={() => (error = null)}>×</button></div>
	{/if}

	{#if loading}
		<div class="empty-state">Cargando…</div>
	{:else if stats && stats.total_seconds === 0}
		<div class="empty-state">
			<div class="empty-icon">🕳️</div>
			Nada perdido todavía. La extensión registrará automáticamente el tiempo que pases en
			Shorts, TikTok, Twitter y Reels.
		</div>
	{:else if stats}
		<div class="content">
			<!-- Ratio señal/ruido -->
			{#if weekRatio !== null}
				<section class="panel">
					<h2 class="panel-title">Señal vs ruido <span class="panel-sub">esta semana</span></h2>
					<div class="ratio-bar">
						<div class="ratio-good" style="width:{weekRatio * 100}%"></div>
					</div>
					<div class="ratio-legend">
						<span class="dot good"></span> Contenido bueno {fmtDur(weekGoodSecs)}
						<span class="dot bad-dot"></span> Basura {fmtDur(weekBadSecs)}
						<span class="ratio-pct">{Math.round(weekRatio * 100)}% señal</span>
					</div>
				</section>
			{/if}

			<!-- Por plataforma -->
			<section class="panel">
				<h2 class="panel-title">De dónde viene la fuga</h2>
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
											· {p.items_count} vídeos
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
			</section>

			<!-- Últimos 30 días -->
			<section class="panel">
				<h2 class="panel-title">Últimos 30 días</h2>
				<div class="chart">
					{#each dailyTotals as day (day.date)}
						<div class="chart-col" title="{day.label}: {fmtDur(day.seconds)}">
							<div
								class="chart-bar"
								style="height:{Math.max(day.seconds > 0 ? 4 : 1, (day.seconds / maxDaily) * 100)}%"
								class:zero={day.seconds === 0}
							></div>
						</div>
					{/each}
				</div>
				<div class="chart-labels">
					<span>{dailyTotals[0]?.label}</span>
					<span>hoy</span>
				</div>
			</section>
		</div>
	{/if}
</div>

<style>
	.page {
		min-height: 100%;
		display: flex;
		flex-direction: column;
	}

	.page-header {
		position: sticky;
		top: 0;
		z-index: 10;
		background: var(--glass-bg-strong);
		backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		-webkit-backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		border-bottom: 1px solid var(--glass-border);
		padding: 20px 20px 16px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.page-header-top {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.page-title {
		font-size: 26px;
		font-weight: 800;
		color: var(--text);
		line-height: 1.1;
	}

	.page-sub {
		font-size: 13px;
		color: var(--text-muted);
		margin-top: 2px;
	}

	.total-hero {
		text-align: center;
		padding: 6px 0 2px;
	}

	.total-value {
		font-size: 54px;
		font-weight: 900;
		line-height: 1;
		letter-spacing: -0.02em;
		color: oklch(0.68 0.2 25);
		text-shadow: 0 0 32px oklch(0.6 0.22 25 / 0.35);
	}

	.total-caption {
		margin-top: 6px;
		font-size: 13px;
		color: var(--text-muted);
	}

	.total-vs {
		margin-top: 2px;
		font-size: 13px;
		color: var(--text-muted);
	}

	.total-vs strong {
		color: oklch(0.72 0.17 150);
		font-weight: 700;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 10px;
	}

	.stat-card {
		background: var(--glass-bg);
		backdrop-filter: blur(16px);
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-xs);
		padding: 12px 14px;
	}

	.stat-label {
		font-size: 11px;
		color: var(--text-dim);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.stat-value {
		font-size: 20px;
		font-weight: 800;
		color: var(--text);
		margin-top: 2px;
	}

	.stat-value.bad {
		color: oklch(0.68 0.2 25);
	}

	.stat-sub {
		font-size: 12px;
		color: var(--text-muted);
		margin-top: 2px;
	}

	.error-banner {
		margin: 16px 20px 0;
		padding: 10px 14px;
		border-radius: var(--radius-xs);
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

	.content {
		padding: 16px 20px 90px;
		display: flex;
		flex-direction: column;
		gap: 14px;
		max-width: 860px;
		width: 100%;
		margin: 0 auto;
	}

	.panel {
		background: var(--glass-bg);
		backdrop-filter: blur(16px);
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-sm, 14px);
		padding: 16px 18px;
	}

	.panel-title {
		font-size: 15px;
		font-weight: 700;
		color: var(--text);
		margin-bottom: 12px;
	}

	.panel-sub {
		font-size: 12px;
		font-weight: 500;
		color: var(--text-dim);
	}

	/* Ratio señal/ruido */
	.ratio-bar {
		height: 14px;
		border-radius: 999px;
		overflow: hidden;
		background: oklch(0.55 0.18 25 / 0.55);
	}

	.ratio-good {
		height: 100%;
		background: oklch(0.72 0.17 150);
		border-radius: 999px 0 0 999px;
		transition: width 0.5s ease;
	}

	.ratio-legend {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px 10px;
		margin-top: 10px;
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
		background: oklch(0.55 0.18 25);
	}

	.ratio-pct {
		margin-left: auto;
		font-weight: 700;
		color: var(--text);
	}

	/* Plataformas */
	.platform-list {
		display: flex;
		flex-direction: column;
		gap: 12px;
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

	/* Gráfica diaria */
	.chart {
		display: flex;
		align-items: flex-end;
		gap: 3px;
		height: 110px;
	}

	.chart-col {
		flex: 1;
		height: 100%;
		display: flex;
		align-items: flex-end;
	}

	.chart-bar {
		width: 100%;
		border-radius: 3px 3px 0 0;
		background: oklch(0.62 0.19 25 / 0.85);
		min-height: 1px;
	}

	.chart-bar.zero {
		background: var(--glass-border);
	}

	.chart-labels {
		display: flex;
		justify-content: space-between;
		margin-top: 6px;
		font-size: 11px;
		color: var(--text-dim);
	}

	@media (max-width: 560px) {
		.stats-row {
			grid-template-columns: 1fr;
		}
		.stat-value {
			font-size: 18px;
		}
	}
</style>
