<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS } from '$lib/utils';
	import type { RewindStats } from '$lib/types';

	const MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
	const DAYS_ES = ['L','M','X','J','V','S','D'];
	const TYPE_COLORS: Record<string, string> = {
		youtube:  'var(--youtube)',
		movie:    'var(--movie)',
		series:   'var(--series)',
		book:     'var(--book)',
		game:     'var(--game)',
		music:    'var(--music)',
	};

	let year = $state(new Date().getFullYear());
	let stats: RewindStats | null = $state(null);
	let loading = $state(false);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
	});

	// Load whenever year or login changes
	$effect(() => {
		const _year = year;
		if (!auth.isLoggedIn) return;
		loading = true;
		stats = null;
		api.get<RewindStats>(`/contents/rewind?year=${_year}`)
			.then(r => { stats = r; })
			.finally(() => { loading = false; });
	});

	// --- Calendar heatmap ---
	type CalDay = {
		date: Date;
		key: string;
		inYear: boolean;
		count: number;
		minutes: number;
	};

	function buildCalendarGrid(yr: number, calendar: RewindStats['calendar']): CalDay[][] {
		const jan1 = new Date(yr, 0, 1);
		const dec31 = new Date(yr, 11, 31);

		// Start on Monday of the week containing Jan 1
		const startDate = new Date(jan1);
		const dow = (jan1.getDay() + 6) % 7; // Mon=0
		startDate.setDate(startDate.getDate() - dow);

		// End on Sunday of the week containing Dec 31
		const endDate = new Date(dec31);
		const edow = (dec31.getDay() + 6) % 7;
		endDate.setDate(endDate.getDate() + (6 - edow));

		const weeks: CalDay[][] = [];
		const cur = new Date(startDate);

		while (cur <= endDate) {
			const week: CalDay[] = [];
			for (let d = 0; d < 7; d++) {
				const key = `${cur.getFullYear()}-${String(cur.getMonth()+1).padStart(2,'0')}-${String(cur.getDate()).padStart(2,'0')}`;
				const dayData = calendar[key];
				week.push({
					date: new Date(cur),
					key,
					inYear: cur.getFullYear() === yr,
					count: dayData?.count ?? 0,
					minutes: dayData?.minutes ?? 0,
				});
				cur.setDate(cur.getDate() + 1);
			}
			weeks.push(week);
		}
		return weeks;
	}

	function heatColor(minutes: number, inYear: boolean): string {
		if (!inYear) return 'transparent';
		if (minutes === 0) return 'rgba(255,255,255,0.05)';
		if (minutes < 60)  return '#0d4f3c';
		if (minutes < 180) return '#1a7a55';
		if (minutes < 360) return '#27ae60';
		return '#4fffaa';
	}

	/** Returns week index (column) where each month starts */
	function monthLabels(weeks: CalDay[][]): { label: string; col: number }[] {
		const seen = new Set<number>();
		const result: { label: string; col: number }[] = [];
		weeks.forEach((week, col) => {
			const firstInYear = week.find(d => d.inYear);
			if (!firstInYear) return;
			const m = firstInYear.date.getMonth();
			if (!seen.has(m) && firstInYear.date.getDate() <= 7) {
				seen.add(m);
				result.push({ label: MONTHS_ES[m], col });
			}
		});
		return result;
	}

	function minutesToDays(minutes: number): string {
		const d = Math.floor(minutes / (60 * 24));
		const h = Math.floor((minutes % (60 * 24)) / 60);
		if (d === 0) return `${h}h`;
		if (h === 0) return `${d} día${d !== 1 ? 's' : ''}`;
		return `${d}d ${h}h`;
	}

	const calendarGrid = $derived(stats ? buildCalendarGrid(year, stats.calendar) : []);
	const calMonthLabels = $derived(monthLabels(calendarGrid));

	// Bar chart max for months
	const maxMonthMinutes = $derived(
		stats ? Math.max(1, ...stats.by_month.map(m => m.minutes)) : 1
	);
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}

<!-- Year picker -->
<div class="year-picker">
	<button class="btn-secondary year-arrow" onclick={() => year--}>‹</button>
	<span class="year-label">Rewind {year}</span>
	<button class="btn-secondary year-arrow" onclick={() => year++} disabled={year >= new Date().getFullYear()}>›</button>
</div>

{#if loading}
	<p style="text-align:center; color:var(--text-muted); margin-top:3rem;">Calculando tu año…</p>

{:else if !stats || stats.total_consumed_count === 0}
	<div class="card empty-state">
		<p style="font-size:2rem; margin-bottom:0.5rem;">🪐</p>
		<p>Sin contenido consumido en {year}.</p>
		<p style="color:var(--text-muted); font-size:0.9rem; margin-top:0.5rem;">
			Marca ítems como consumidos para verlos aquí.
		</p>
	</div>

{:else}

<!-- Hero -->
<div class="hero-number" style="margin-bottom:0.5rem;">
	<div class="kicker">TU AÑO EN CONTENIDO</div>
	<div class="number">{stats.total_consumed_count}</div>
	<div class="unit">
		{stats.total_consumed_count === 1 ? 'ítem consumido' : 'ítems consumidos'} ·
		{formatDuration(stats.total_consumed_minutes)}
	</div>
</div>

<div class="card pct-card">
	<span class="pct-number">{stats.percentage_of_year.toFixed(2)}%</span>
	<span class="pct-label">de tu año {year} dedicado a contenido</span>
	<span class="pct-sub">≈ {minutesToDays(stats.total_consumed_minutes)}</span>
</div>

<!-- By type -->
{#if Object.keys(stats.by_type).length > 0}
<section class="section">
	<h2 class="section-title">Por tipo</h2>
	<div class="type-grid">
		{#each Object.entries(stats.by_type).sort((a,b) => b[1].minutes - a[1].minutes) as [type, s]}
			<div class="type-card" style="border-color:{TYPE_COLORS[type] ?? 'var(--border)'}20; background: {TYPE_COLORS[type] ?? 'var(--primary)'}0d;">
				<div class="type-icon">{TYPE_ICONS[type] ?? '📄'}</div>
				<div class="type-name">{TYPE_LABELS[type] ?? type}</div>
				<div class="type-count">{s.count} ítem{s.count !== 1 ? 's' : ''}</div>
				<div class="type-time">{formatDuration(s.minutes)}</div>
				<div class="type-pct" style="color:{TYPE_COLORS[type] ?? 'var(--primary)'}">
					{s.percentage_of_year < 0.01 ? '<0.01' : s.percentage_of_year.toFixed(2)}% del año
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Heatmap calendar -->
<section class="section">
	<h2 class="section-title">Actividad diaria</h2>
	<div class="heatmap-wrap">
		<!-- Month labels row -->
		<div class="heatmap-months" style="grid-template-columns: 28px repeat({calendarGrid.length}, 12px);">
			<div></div><!-- spacer for day labels column -->
			{#each calendarGrid as _, col}
				{@const label = calMonthLabels.find(m => m.col === col)}
				<div class="month-label">{label ? label.label : ''}</div>
			{/each}
		</div>

		<!-- Day labels + grid -->
		<div class="heatmap-body">
			<!-- Day-of-week labels -->
			<div class="day-labels">
				{#each DAYS_ES as d, i}
					{#if i % 2 === 0}
						<div class="day-label">{d}</div>
					{:else}
						<div class="day-label"></div>
					{/if}
				{/each}
			</div>

			<!-- Week columns -->
			<div class="heatmap-grid">
				{#each calendarGrid as week}
					<div class="week-col">
						{#each week as day}
							<div
								class="heat-cell"
								style="background:{heatColor(day.minutes, day.inYear)}"
								title={day.inYear && day.count > 0
									? `${day.key}: ${day.count} ítem${day.count !== 1 ? 's' : ''} · ${formatDuration(day.minutes)}`
									: day.key}
							></div>
						{/each}
					</div>
				{/each}
			</div>
		</div>

		<!-- Legend -->
		<div class="heat-legend">
			<span>Menos</span>
			<div class="heat-cell legend-cell" style="background:rgba(255,255,255,0.05)"></div>
			<div class="heat-cell legend-cell" style="background:#0d4f3c"></div>
			<div class="heat-cell legend-cell" style="background:#1a7a55"></div>
			<div class="heat-cell legend-cell" style="background:#27ae60"></div>
			<div class="heat-cell legend-cell" style="background:#4fffaa"></div>
			<span>Más</span>
		</div>
	</div>
</section>

<!-- Month breakdown -->
<section class="section">
	<h2 class="section-title">Por mes</h2>
	<div class="months-chart">
		{#each stats.by_month as m}
			{@const pct = m.minutes / maxMonthMinutes * 100}
			<div class="month-bar-wrap" title="{MONTHS_ES[m.month-1]}: {m.count} ítems · {formatDuration(m.minutes)}">
				<div class="month-bar-col">
					<div class="month-bar" style="height:{pct}%; background: var(--primary); opacity:{m.minutes > 0 ? 0.85 : 0.12};"></div>
				</div>
				<div class="month-bar-label">{MONTHS_ES[m.month-1]}</div>
				{#if m.count > 0}
					<div class="month-bar-count">{m.count}</div>
				{/if}
			</div>
		{/each}
	</div>
</section>

<!-- Item list -->
<section class="section">
	<h2 class="section-title">Todo lo consumido</h2>
	<div style="display:flex; flex-direction:column; gap:0.4rem;">
		{#each stats.items as c (c.id)}
			<div class="rewind-item">
				{#if c.thumbnail}
					<img class="rewind-thumb" src={c.thumbnail} alt="" />
				{:else}
					<div class="rewind-thumb" style="display:flex;align-items:center;justify-content:center;font-size:1.1rem;">
						{TYPE_ICONS[c.content_type] ?? '📄'}
					</div>
				{/if}
				<div class="rewind-item-info">
					<div class="rewind-item-title">{c.title}</div>
					<div class="rewind-item-meta">
						<span class="badge {c.content_type}">{TYPE_LABELS[c.content_type]}</span>
						{#if c.duration_minutes > 0}<span>⏱ {formatDuration(c.duration_minutes)}</span>{/if}
						{#if c.author}<span>{c.author}</span>{/if}
						{#if c.consumed_at}
							<span>📅 {new Date(c.consumed_at).toLocaleDateString('es', { day:'numeric', month:'short' })}</span>
						{/if}
					</div>
				</div>
			</div>
		{/each}
	</div>
</section>

{/if}
{/if}

<style>
	.year-picker {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		margin: 0.5rem 0 1.5rem;
	}
	.year-label {
		font-size: 1.2rem;
		font-weight: 700;
		color: var(--primary);
		min-width: 140px;
		text-align: center;
	}
	.year-arrow {
		padding: 0.3rem 0.8rem;
		font-size: 1.2rem;
		line-height: 1;
	}

	.empty-state {
		text-align: center;
		padding: 3rem 1rem;
		margin-top: 1rem;
	}

	.pct-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1.25rem;
		margin-bottom: 1.5rem;
		gap: 0.2rem;
	}
	.pct-number {
		font-size: 2.5rem;
		font-weight: 900;
		color: var(--primary);
		line-height: 1;
	}
	.pct-label {
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.pct-sub {
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	.section { margin-bottom: 2rem; }
	.section-title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-muted);
		margin-bottom: 0.75rem;
	}

	/* Type grid */
	.type-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
		gap: 0.6rem;
	}
	.type-card {
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.type-icon { font-size: 1.4rem; }
	.type-name { font-size: 0.8rem; font-weight: 600; }
	.type-count { font-size: 0.75rem; color: var(--text-muted); }
	.type-time { font-size: 0.9rem; font-weight: 700; }
	.type-pct { font-size: 0.75rem; font-weight: 600; margin-top: 0.2rem; }

	/* Heatmap */
	.heatmap-wrap {
		overflow-x: auto;
		padding-bottom: 0.5rem;
	}
	.heatmap-months {
		display: grid;
		gap: 2px;
		margin-bottom: 2px;
		min-width: max-content;
	}
	.month-label {
		font-size: 0.6rem;
		color: var(--text-muted);
		text-align: left;
		white-space: nowrap;
	}
	.heatmap-body {
		display: flex;
		gap: 4px;
		min-width: max-content;
	}
	.day-labels {
		display: flex;
		flex-direction: column;
		gap: 2px;
		width: 12px;
	}
	.day-label {
		height: 10px;
		font-size: 0.55rem;
		color: var(--text-muted);
		line-height: 10px;
	}
	.heatmap-grid {
		display: flex;
		gap: 2px;
	}
	.week-col {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.heat-cell {
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}
	.heat-legend {
		display: flex;
		align-items: center;
		gap: 3px;
		margin-top: 0.5rem;
		font-size: 0.65rem;
		color: var(--text-muted);
	}
	.legend-cell {
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}

	/* Month bar chart */
	.months-chart {
		display: flex;
		gap: 4px;
		align-items: flex-end;
		height: 100px;
		padding-bottom: 28px;
		position: relative;
	}
	.month-bar-wrap {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		height: 100%;
		justify-content: flex-end;
		position: relative;
		cursor: default;
	}
	.month-bar-col {
		width: 100%;
		flex: 1;
		display: flex;
		align-items: flex-end;
	}
	.month-bar {
		width: 100%;
		min-height: 2px;
		border-radius: 4px 4px 0 0;
		transition: opacity 0.2s;
	}
	.month-bar-label {
		position: absolute;
		bottom: 0;
		font-size: 0.6rem;
		color: var(--text-muted);
		white-space: nowrap;
	}
	.month-bar-count {
		position: absolute;
		bottom: 12px;
		font-size: 0.6rem;
		color: var(--primary);
		font-weight: 700;
	}

	/* Item list */
	.rewind-item {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		padding: 0.4rem 0.5rem;
		border-radius: 10px;
		background: var(--surface2);
	}
	.rewind-thumb {
		width: 40px;
		height: 40px;
		object-fit: cover;
		border-radius: 6px;
		flex-shrink: 0;
		background: var(--surface);
	}
	.rewind-item-info { flex: 1; min-width: 0; }
	.rewind-item-title {
		font-size: 0.85rem;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.rewind-item-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.2rem;
		font-size: 0.72rem;
		color: var(--text-muted);
	}
</style>
