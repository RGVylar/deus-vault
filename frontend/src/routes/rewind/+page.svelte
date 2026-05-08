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

	function heatLevel(minutes: number, inYear: boolean): string {
		if (!inYear || minutes === 0) return '';
		if (minutes < 60)  return 'l1';
		if (minutes < 180) return 'l2';
		if (minutes < 360) return 'l3';
		return 'l4';
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

	// Max streaming minutes (for bar width %)
	const maxStreamingMins = $derived(
		stats?.streaming_breakdown.length
			? Math.max(1, ...stats.streaming_breakdown.map(p => p.minutes))
			: 1
	);
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">Redirigiendo…</p>
{:else}

<!-- Desktop topbar -->
<div class="desk-topbar desk-only">
	<h1 class="desk-title">Rewind {year}</h1>
	<div class="desk-spacer"></div>
	<button class="btn" onclick={() => year--}>‹ Anterior</button>
	<button class="btn" onclick={() => year++} disabled={year >= new Date().getFullYear()}>Siguiente ›</button>
</div>

<!-- Year picker (mobile) -->
<div class="row mobile-only" style="justify-content:center; margin:8px 0 20px; gap:16px;">
	<button class="btn" onclick={() => year--}>‹</button>
	<span style="font-size:18px; font-weight:700; color:var(--primary); min-width:140px; text-align:center;">Rewind {year}</span>
	<button class="btn" onclick={() => year++} disabled={year >= new Date().getFullYear()}>›</button>
</div>

{#if loading}
	<p class="muted center" style="margin-top:3rem;">Calculando tu año…</p>

{:else if !stats || stats.total_consumed_count === 0}
	<div class="glass empty">
		<span class="icon">🪐</span>
		<p>Sin contenido consumido en {year}.</p>
		<p class="muted" style="font-size:13px; margin-top:6px;">Marca ítems como consumidos para verlos aquí.</p>
	</div>

{:else}

<!-- Mobile hero -->
<div class="hero mobile-only" style="padding: 20px 12px 8px;">
	<div class="kicker">TU AÑO EN CONTENIDO</div>
	<div class="number" style="font-size:clamp(64px,20vw,100px); background:linear-gradient(180deg,#fff,oklch(0.78 0.18 300)); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; filter:drop-shadow(0 0 28px oklch(0.75 0.18 300 / 0.5));">{stats.total_consumed_count}</div>
	<div class="unit">{stats.total_consumed_count === 1 ? 'ítem consumido' : 'ítems consumidos'} · {formatDuration(stats.total_consumed_minutes)}</div>
	<div class="sub">{stats.percentage_of_year.toFixed(2)}% de tu año · ≈ {minutesToDays(stats.total_consumed_minutes)}</div>
</div>

<!-- Desktop rewind grid -->
<div class="desk-rewind-grid desk-only">

	<!-- Hero row: spans full width on desktop -->
	<div class="desk-rewind-hero">
		<!-- Hero number card -->
		<div class="desk-hero">
			<div class="kicker">TU AÑO EN CONTENIDO</div>
			<div class="number" style="font-size:clamp(72px,7vw,120px);">{stats.total_consumed_count}</div>
			<div class="unit">{stats.total_consumed_count === 1 ? 'ítem consumido' : 'ítems consumidos'} · {formatDuration(stats.total_consumed_minutes)}</div>
			<div class="sub">{stats.percentage_of_year.toFixed(2)}% de tu año · ≈ {minutesToDays(stats.total_consumed_minutes)}</div>
		</div>

		<!-- % + estats card -->
		<div class="desk-quick">
			<div style="text-align:center; font-size:52px; font-weight:900; color:var(--primary); line-height:1; filter:drop-shadow(0 0 24px oklch(0.75 0.18 300 / 0.5)); letter-spacing:-0.04em;">{stats.percentage_of_year.toFixed(2)}%</div>
			<div class="muted center" style="font-size:13px; margin-top:6px;">de tu año dedicado a contenido</div>
			<div class="muted center" style="font-size:12px;">≈ {minutesToDays(stats.total_consumed_minutes)}</div>
			<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:16px;">
				{#if stats.streak_current > 0}
					<div class="estat" style="min-width:0;"><div class="ei">🔥</div><div class="ev">{stats.streak_current}</div><div class="el">racha actual</div></div>
				{/if}
				{#if stats.streak_max > 0}
					<div class="estat" style="min-width:0;"><div class="ei">⚡</div><div class="ev">{stats.streak_max}</div><div class="el">racha máx</div></div>
				{/if}
				{#if stats.best_month !== null}
					<div class="estat" style="min-width:0;"><div class="ei">🏆</div><div class="ev">{MONTHS_ES[(stats.best_month ?? 1) - 1]}</div><div class="el">mejor mes</div></div>
				{/if}
				{#if stats.favorite_type}
					<div class="estat" style="min-width:0;"><div class="ei">{TYPE_ICONS[stats.favorite_type] ?? '📄'}</div><div class="ev">{TYPE_LABELS[stats.favorite_type] ?? stats.favorite_type}</div><div class="el">favorito</div></div>
				{/if}
				{#if stats.completion_rate !== null}
					<div class="estat" style="min-width:0;"><div class="ei">📊</div><div class="ev">{stats.completion_rate}%</div><div class="el">tasa éxito</div></div>
				{/if}
				{#if stats.abandoned_count > 0}
					<div class="estat" style="min-width:0;"><div class="ei">🚫</div><div class="ev">{stats.abandoned_count}</div><div class="el">abandonados</div></div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Month bars card -->
	<div class="glass" style="padding:20px;">
		<div class="rw-label">Por mes</div>
		<div class="month-bars desk-month-bars">
			{#each stats.by_month as m}
				{@const pct = m.minutes / maxMonthMinutes * 100}
				<div class="mb-col" title="{MONTHS_ES[m.month-1]}: {m.count} ítems · {formatDuration(m.minutes)}">
					<div class="mb-bar" style="height:{Math.max(pct, m.minutes > 0 ? 3 : 0)}%; opacity:{m.minutes > 0 ? 1 : 0.15};"></div>
					<div class="mb-lbl">{MONTHS_ES[m.month-1]}</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- Heatmap card -->
	<div class="glass" style="padding:18px; overflow-x:auto;">
		<div class="rw-label">Actividad diaria</div>
		<div style="grid-template-columns: 20px repeat({calendarGrid.length}, 12px); display:grid; gap:2px; margin-bottom:2px; min-width:max-content;">
			<div></div>
			{#each calendarGrid as _, col}
				{@const label = calMonthLabels.find(m => m.col === col)}
				<div style="font-size:9px; color:var(--text-muted);">{label ? label.label : ''}</div>
			{/each}
		</div>
		<div style="display:flex; gap:4px; min-width:max-content;">
			<div style="display:flex; flex-direction:column; gap:2px; width:12px;">
				{#each DAYS_ES as d, i}
					<div style="height:10px; font-size:8px; color:var(--text-muted); line-height:10px;">{i % 2 === 0 ? d : ''}</div>
				{/each}
			</div>
			<div style="display:flex; gap:2px;">
				{#each calendarGrid as week}
					<div style="display:flex; flex-direction:column; gap:2px;">
						{#each week as day}
							<div
								class="heat {heatLevel(day.minutes, day.inYear)}"
								style="width:10px; height:10px;{!day.inYear ? 'background:transparent; border-color:transparent;' : ''}"
								title={day.inYear && day.count > 0 ? `${day.key}: ${day.count} ítem${day.count !== 1 ? 's' : ''} · ${formatDuration(day.minutes)}` : day.key}
							></div>
						{/each}
					</div>
				{/each}
			</div>
		</div>
		<div style="display:flex; align-items:center; gap:4px; margin-top:8px; font-size:10px; color:var(--text-muted); justify-content:flex-end;">
			<span>menos</span>
			<div class="heat" style="width:10px;height:10px;"></div>
			<div class="heat l1" style="width:10px;height:10px;"></div>
			<div class="heat l2" style="width:10px;height:10px;"></div>
			<div class="heat l3" style="width:10px;height:10px;"></div>
			<div class="heat l4" style="width:10px;height:10px;"></div>
			<span>más</span>
		</div>
	</div>

</div><!-- /desk-rewind-grid -->

<!-- Mobile-only estat chips -->
<div class="estat-grid mobile-only">
	{#if stats.streak_current > 0}
		<div class="estat"><div class="ei">🔥</div><div class="ev">{stats.streak_current}</div><div class="el">días seguidos</div></div>
	{/if}
	{#if stats.streak_max > 0}
		<div class="estat"><div class="ei">⚡</div><div class="ev">{stats.streak_max}</div><div class="el">racha máx.</div></div>
	{/if}
	{#if stats.best_month !== null}
		<div class="estat"><div class="ei">🏆</div><div class="ev">{MONTHS_ES[(stats.best_month ?? 1) - 1]}</div><div class="el">mejor mes</div></div>
	{/if}
	{#if stats.avg_days_to_consume !== null}
		<div class="estat"><div class="ei">⏳</div><div class="ev">{stats.avg_days_to_consume}d</div><div class="el">media a terminar</div></div>
	{/if}
	{#if stats.favorite_type}
		<div class="estat"><div class="ei">{TYPE_ICONS[stats.favorite_type] ?? '📄'}</div><div class="ev">{TYPE_LABELS[stats.favorite_type] ?? stats.favorite_type}</div><div class="el">favorito</div></div>
	{/if}
	{#if stats.completion_rate !== null}
		<div class="estat"><div class="ei">📊</div><div class="ev">{stats.completion_rate}%</div><div class="el">tasa éxito</div></div>
	{/if}
	{#if stats.abandoned_count > 0}
		<div class="estat"><div class="ei">🚫</div><div class="ev">{stats.abandoned_count}</div><div class="el">abandonados</div></div>
	{/if}
</div>

<!-- Mobile heatmap -->
<section class="rewind-section mobile-only">
	<h2>Actividad diaria</h2>
	<div class="glass" style="overflow-x:auto; padding:12px;">
		<div style="grid-template-columns: 20px repeat({calendarGrid.length}, 12px); display:grid; gap:2px; margin-bottom:2px; min-width:max-content;">
			<div></div>
			{#each calendarGrid as _, col}
				{@const label = calMonthLabels.find(m => m.col === col)}
				<div style="font-size:9px; color:var(--text-muted);">{label ? label.label : ''}</div>
			{/each}
		</div>
		<div style="display:flex; gap:4px; min-width:max-content;">
			<div style="display:flex; flex-direction:column; gap:2px; width:12px;">
				{#each DAYS_ES as d, i}
					<div style="height:10px; font-size:8px; color:var(--text-muted); line-height:10px;">{i % 2 === 0 ? d : ''}</div>
				{/each}
			</div>
			<div style="display:flex; gap:2px;">
				{#each calendarGrid as week}
					<div style="display:flex; flex-direction:column; gap:2px;">
						{#each week as day}
							<div class="heat {heatLevel(day.minutes, day.inYear)}"
								style="width:10px; height:10px;{!day.inYear ? 'background:transparent; border-color:transparent;' : ''}"
								title={day.inYear && day.count > 0 ? `${day.key}: ${day.count} ítem${day.count !== 1 ? 's' : ''} · ${formatDuration(day.minutes)}` : day.key}
							></div>
						{/each}
					</div>
				{/each}
			</div>
		</div>
		<div style="display:flex; align-items:center; gap:4px; margin-top:8px; font-size:10px; color:var(--text-muted);">
			<span>Menos</span>
			<div class="heat" style="width:10px;height:10px;"></div><div class="heat l1" style="width:10px;height:10px;"></div>
			<div class="heat l2" style="width:10px;height:10px;"></div><div class="heat l3" style="width:10px;height:10px;"></div>
			<div class="heat l4" style="width:10px;height:10px;"></div><span>Más</span>
		</div>
	</div>
</section>

<!-- Mobile month bars -->
<section class="rewind-section mobile-only">
	<h2>Por mes</h2>
	<div class="glass" style="padding:16px;">
		<div class="month-bars">
			{#each stats.by_month as m}
				{@const pct = m.minutes / maxMonthMinutes * 100}
				<div class="mb-col" title="{MONTHS_ES[m.month-1]}: {m.count} ítems · {formatDuration(m.minutes)}">
					<div class="mb-bar" style="height:{Math.max(pct, m.minutes > 0 ? 3 : 0)}%; opacity:{m.minutes > 0 ? 1 : 0.15};"></div>
					<div class="mb-lbl">{MONTHS_ES[m.month-1]}</div>
				</div>
			{/each}
		</div>
	</div>
</section>

<!-- ══════════════════════════════════════════════════════ -->
<!-- DEEP STATS — desktop-first, collapsible on mobile   -->
<!-- ══════════════════════════════════════════════════════ -->

<!-- YouTube: top channels -->
{#if stats.top_youtube_channels.length > 0}
<section class="rewind-section deep-section">
	<h2>▶️ Canales más vistos</h2>
	<div class="deep-grid">
		{#each stats.top_youtube_channels as ch, i}
			<div class="deep-card" style="--accent:var(--youtube);">
				<div class="dc-rank">#{i + 1}</div>
				<div class="dc-body">
					<div class="dc-name">{ch.name}</div>
					<div class="dc-meta">{ch.count} vídeo{ch.count !== 1 ? 's' : ''}</div>
				</div>
				<div class="dc-time">{formatDuration(ch.minutes)}</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top items: YouTube -->
{#if stats.top_items_by_type['youtube']?.length > 0}
<section class="rewind-section deep-section">
	<h2>▶️ Vídeos más largos</h2>
	<div class="top-items-grid">
		{#each stats.top_items_by_type['youtube'] as item, i}
			<div class="top-item-card" style="--accent:var(--youtube);">
				<div class="tic-rank">#{i + 1}</div>
				{#if item.thumbnail}
					<img class="tic-thumb" src={item.thumbnail} alt="" />
				{:else}
					<div class="tic-thumb tic-ph">▶️</div>
				{/if}
				<div class="tic-info">
					<div class="tic-title">{item.title}</div>
					{#if item.author}<div class="tic-author">{item.author}</div>{/if}
					<div class="tic-time">{formatDuration(item.minutes)}</div>
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Streaming breakdown -->
{#if stats.streaming_breakdown.length > 0}
<section class="rewind-section deep-section">
	<h2>🎬 Plataformas de streaming</h2>
	<div class="deep-grid">
		{#each stats.streaming_breakdown as plat, i}
			<div class="deep-card" style="--accent:var(--movie);">
				<div class="dc-rank">#{i + 1}</div>
				<div class="dc-body">
					<div class="dc-name">{plat.name}</div>
					<div class="dc-bar-wrap">
						<div class="dc-bar" style="width:{Math.round(plat.minutes / maxStreamingMins * 100)}%; background:var(--movie);"></div>
					</div>
					<div class="dc-meta">{plat.count} título{plat.count !== 1 ? 's' : ''}</div>
				</div>
				<div class="dc-time">{formatDuration(plat.minutes)}</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top movies -->
{#if stats.top_items_by_type['movie']?.length > 0}
<section class="rewind-section deep-section">
	<h2>🎬 Películas más largas</h2>
	<div class="top-items-grid">
		{#each stats.top_items_by_type['movie'] as item, i}
			<div class="top-item-card" style="--accent:var(--movie);">
				<div class="tic-rank">#{i + 1}</div>
				{#if item.thumbnail}
					<img class="tic-thumb" src={item.thumbnail} alt="" />
				{:else}
					<div class="tic-thumb tic-ph">🎬</div>
				{/if}
				<div class="tic-info">
					<div class="tic-title">{item.title}</div>
					{#if item.author}<div class="tic-author">{item.author}</div>{/if}
					<div class="tic-time">{formatDuration(item.minutes)}</div>
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top series -->
{#if stats.top_items_by_type['series']?.length > 0}
<section class="rewind-section deep-section">
	<h2>📺 Series más largas</h2>
	<div class="top-items-grid">
		{#each stats.top_items_by_type['series'] as item, i}
			<div class="top-item-card" style="--accent:var(--series);">
				<div class="tic-rank">#{i + 1}</div>
				{#if item.thumbnail}
					<img class="tic-thumb" src={item.thumbnail} alt="" />
				{:else}
					<div class="tic-thumb tic-ph">📺</div>
				{/if}
				<div class="tic-info">
					<div class="tic-title">{item.title}</div>
					{#if item.author}<div class="tic-author">{item.author}</div>{/if}
					<div class="tic-time">{formatDuration(item.minutes)}</div>
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top book authors -->
{#if stats.top_book_authors.length > 0}
<section class="rewind-section deep-section">
	<h2>📖 Autores más leídos</h2>
	<div class="deep-grid">
		{#each stats.top_book_authors as author, i}
			<div class="deep-card" style="--accent:var(--book);">
				<div class="dc-rank">#{i + 1}</div>
				<div class="dc-body">
					<div class="dc-name">{author.name}</div>
					<div class="dc-meta">{author.count} libro{author.count !== 1 ? 's' : ''}</div>
				</div>
				<div class="dc-time">{formatDuration(author.minutes)}</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top books -->
{#if stats.top_items_by_type['book']?.length > 0}
<section class="rewind-section deep-section">
	<h2>📖 Libros más largos</h2>
	<div class="top-items-grid">
		{#each stats.top_items_by_type['book'] as item, i}
			<div class="top-item-card" style="--accent:var(--book);">
				<div class="tic-rank">#{i + 1}</div>
				{#if item.thumbnail}
					<img class="tic-thumb tic-thumb-port" src={item.thumbnail} alt="" />
				{:else}
					<div class="tic-thumb tic-ph">📖</div>
				{/if}
				<div class="tic-info">
					<div class="tic-title">{item.title}</div>
					{#if item.author}<div class="tic-author">{item.author}</div>{/if}
					<div class="tic-time">{formatDuration(item.minutes)}</div>
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Top games -->
{#if stats.top_items_by_type['game']?.length > 0}
<section class="rewind-section deep-section">
	<h2>🎮 Juegos más largos</h2>
	<div class="top-items-grid">
		{#each stats.top_items_by_type['game'] as item, i}
			<div class="top-item-card" style="--accent:var(--game);">
				<div class="tic-rank">#{i + 1}</div>
				{#if item.thumbnail}
					<img class="tic-thumb" src={item.thumbnail} alt="" />
				{:else}
					<div class="tic-thumb tic-ph">🎮</div>
				{/if}
				<div class="tic-info">
					<div class="tic-title">{item.title}</div>
					{#if item.author}<div class="tic-author">{item.author}</div>{/if}
					<div class="tic-time">{formatDuration(item.minutes)}</div>
				</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- By type (auto-fill grid, shared) -->
{#if Object.keys(stats.by_type).length > 0}
<section class="rewind-section">
	<h2>Por tipo</h2>
	<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(160px,1fr)); gap:10px;">
		{#each Object.entries(stats.by_type).sort((a,b) => b[1].minutes - a[1].minutes) as [type, s]}
			<div class="type-card" style="--accent:{TYPE_COLORS[type] ?? 'var(--primary)'}; padding:16px;">
				<div class="ico" style="font-size:24px;">{TYPE_ICONS[type] ?? '📄'}</div>
				<div class="nm" style="font-size:13px;">{TYPE_LABELS[type] ?? type}</div>
				<div class="ct">{s.count} ítem{s.count !== 1 ? 's' : ''}</div>
				<div class="tm" style="font-size:18px;">{formatDuration(s.minutes)}</div>
				<div class="pc">{s.percentage_of_year < 0.01 ? '<0.01' : s.percentage_of_year.toFixed(2)}% del año</div>
			</div>
		{/each}
	</div>
</section>
{/if}

<!-- Item list -->
<section class="rewind-section">
	<h2>Todo lo consumido</h2>
	<div class="content-grid">
		{#each stats.items as c (c.id)}
			{@const landscape = c.content_type === 'youtube' || c.content_type === 'movie' || c.content_type === 'series' || c.content_type === 'game'}
			<div
				class="c-card"
				class:landscape
				class:portrait={!landscape}
				style="--card-accent:{TYPE_COLORS[c.content_type] ?? 'var(--primary)'}; --accent:{TYPE_COLORS[c.content_type] ?? 'var(--primary)'}"
			>
				{#if landscape}
					<div class="thumb-land">
						{#if c.thumbnail}<img src={c.thumbnail} alt="" />{:else}<div class="ph">{TYPE_ICONS[c.content_type] ?? '📄'}</div>{/if}
					</div>
				{:else}
					<div class="thumb-port">
						{#if c.thumbnail}<img src={c.thumbnail} alt="" />{:else}<div class="ph">{TYPE_ICONS[c.content_type] ?? '📄'}</div>{/if}
					</div>
				{/if}
				<div class="info">
					<div class="title">{c.title}</div>
					<div class="meta">
						<span class="badge">{TYPE_LABELS[c.content_type]}</span>
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
	.rewind-section { margin-bottom: 28px; }
	.rewind-section h2 {
		font-size: 11px; font-weight: 700; text-transform: uppercase;
		letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 10px;
	}
	.rw-label {
		font-size: 11px; font-weight: 700; text-transform: uppercase;
		letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 14px;
	}

	/* ── Deep stats sections ── */
	.deep-section { }

	/* Ranking cards (channels, platforms, authors) */
	.deep-grid {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.deep-card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		background: var(--glass-bg);
		border: 1px solid var(--glass-border);
		border-radius: 16px;
		backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		-webkit-backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		transition: border-color 0.15s;
	}
	.deep-card:hover { border-color: var(--glass-border-bright); }
	.dc-rank {
		font-size: 11px; font-weight: 800; color: var(--accent, var(--primary));
		min-width: 24px; text-align: center; opacity: 0.8;
	}
	.dc-body { flex: 1; min-width: 0; }
	.dc-name { font-size: 14px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.dc-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
	.dc-time { font-size: 13px; font-weight: 700; color: var(--accent, var(--primary)); white-space: nowrap; }
	.dc-bar-wrap {
		height: 3px; background: var(--glass-border); border-radius: 2px;
		margin: 6px 0 4px; overflow: hidden;
	}
	.dc-bar { height: 100%; border-radius: 2px; opacity: 0.8; transition: width 0.6s ease; }

	/* Top-3 item cards (with thumbnail) */
	.top-items-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 10px;
	}
	.top-item-card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px 10px 10px;
		background: var(--glass-bg);
		border: 1px solid var(--glass-border);
		border-left: 3px solid var(--accent, var(--primary));
		border-radius: 16px;
		backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		-webkit-backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		transition: border-color 0.15s;
	}
	.top-item-card:hover { background: var(--glass-bg-strong); }
	.tic-rank {
		font-size: 18px; font-weight: 900; color: var(--accent, var(--primary));
		min-width: 28px; text-align: center; opacity: 0.6;
	}
	.tic-thumb {
		width: 56px; height: 40px; object-fit: cover;
		border-radius: 8px; flex-shrink: 0;
	}
	.tic-thumb-port {
		width: 32px; height: 48px; object-fit: cover; border-radius: 6px;
	}
	.tic-ph {
		display: flex; align-items: center; justify-content: center;
		background: var(--glass-bg-weak); font-size: 20px;
	}
	.tic-info { flex: 1; min-width: 0; }
	.tic-title { font-size: 14px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tic-author { font-size: 11px; color: var(--text-muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tic-time { font-size: 12px; font-weight: 700; color: var(--accent, var(--primary)); margin-top: 4px; }

	@media (min-width: 1024px) {
		/* On desktop, pair sections side by side */
		.deep-section { }
		.top-items-grid {
			grid-template-columns: repeat(3, 1fr);
		}
		.deep-grid {
			display: grid;
			grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		}
	}
</style>
