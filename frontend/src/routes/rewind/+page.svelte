<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_LABELS } from '$lib/utils';
	import type { RewindStats } from '$lib/types';
	import Icon from '$lib/components/Icon.svelte';
	import Chapter from '$lib/components/Chapter.svelte';
	import { exportShareImage } from '$lib/rewindShare';

	const MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
	const DAYS_ES = ['L','M','X','J','V','S','D'];
	const DAYS_FULL = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];

	// Icono de línea por tipo de contenido (sustituye TYPE_ICONS emoji)
	const TYPE_ICON: Record<string, string> = {
		youtube: 'play', movie: 'film', series: 'tv', music: 'music', book: 'book', game: 'game',
	};
	const TYPE_COLORS: Record<string, string> = {
		youtube: 'var(--youtube)', movie: 'var(--movie)', series: 'var(--series)',
		book: 'var(--book)', game: 'var(--game)', music: 'var(--music)',
	};
	const PLATFORM_COLORS: Record<string, string> = {
		'Netflix': '#e50914', 'Prime Video': '#00a8e1', 'Disney+': '#113ccf',
		'HBO': 'oklch(0.72 0.19 40)', 'Max': 'oklch(0.72 0.19 40)', 'Crunchyroll': '#f47521',
		'Apple TV+': 'rgba(230,230,230,0.85)', 'Movistar+': 'oklch(0.72 0.19 220)',
		'Filmin': 'oklch(0.76 0.18 280)', 'SkyShowtime': 'oklch(0.78 0.18 200)',
	};

	/** Hue determinista a partir de un string → color oklch brillante para avatares */
	function channelColor(name: string): string {
		let h = 0;
		for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff;
		return `oklch(0.72 0.20 ${h % 360})`;
	}

	let year = $state(new Date().getFullYear());
	let stats: RewindStats | null = $state(null);
	let loading = $state(false);
	let loadError = $state<string | null>(null);
	let itemsVisible = $state(12);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
	});

	$effect(() => {
		const _year = year;
		if (!auth.isLoggedIn) return;
		loading = true;
		stats = null;
		loadError = null;
		itemsVisible = 12;
		api.get<RewindStats>(`/contents/rewind?year=${_year}`)
			.then(r => {
				stats = r;
				const hasMissing = r.top_youtube_channels.some(ch => !ch.thumbnail);
				if (hasMissing) {
					api.post('/contents/backfill-channel-thumbnails')
						.then(() => api.get<RewindStats>(`/contents/rewind?year=${_year}`))
						.then(r2 => { stats = r2; })
						.catch(() => {});
				}
			})
			.catch(e => { loadError = e?.message ?? 'Error cargando Rewind'; })
			.finally(() => { loading = false; });
	});

	// ── Calendar heatmap ──────────────────────────────────────────
	type CalDay = { date: Date; key: string; inYear: boolean; count: number; minutes: number };

	function buildCalendarGrid(yr: number, calendar: RewindStats['calendar']): CalDay[][] {
		const jan1 = new Date(yr, 0, 1);
		const dec31 = new Date(yr, 11, 31);
		const startDate = new Date(jan1);
		startDate.setDate(startDate.getDate() - ((jan1.getDay() + 6) % 7));
		const endDate = new Date(dec31);
		endDate.setDate(endDate.getDate() + (6 - ((dec31.getDay() + 6) % 7)));
		const weeks: CalDay[][] = [];
		const cur = new Date(startDate);
		while (cur <= endDate) {
			const week: CalDay[] = [];
			for (let d = 0; d < 7; d++) {
				const key = `${cur.getFullYear()}-${String(cur.getMonth()+1).padStart(2,'0')}-${String(cur.getDate()).padStart(2,'0')}`;
				const dayData = calendar[key];
				week.push({
					date: new Date(cur), key,
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
	const maxMonthMinutes = $derived(stats ? Math.max(1, ...stats.by_month.map(m => m.minutes)) : 1);
	const maxStreamingMins = $derived(
		stats?.streaming_breakdown.length ? Math.max(1, ...stats.streaming_breakdown.map(p => p.minutes)) : 1
	);
	const maxHour = $derived(stats?.by_hour?.length ? Math.max(1, ...stats.by_hour) : 1);
	const maxDay  = $derived(stats?.by_day?.length  ? Math.max(1, ...stats.by_day)  : 1);

	// Índices destacados (mes pico / día pico)
	const topMonthIdx = $derived.by(() => {
		if (!stats?.by_month?.length) return -1;
		let mi = 0;
		stats.by_month.forEach((m, i) => { if (m.minutes > stats!.by_month[mi].minutes) mi = i; });
		return stats.by_month[mi].minutes > 0 ? mi : -1;
	});
	const topDayIdx = $derived(stats?.by_day?.length ? stats.by_day.indexOf(Math.max(...stats.by_day)) : -1);

	// Reparto por tipo
	const typeSorted = $derived(stats ? Object.entries(stats.by_type).sort((a, b) => b[1].minutes - a[1].minutes) : []);
	const typeTotal = $derived(stats ? (Object.values(stats.by_type).reduce((a, t) => a + t.minutes, 0) || 1) : 1);

	// ── Zona YouTube ──────────────────────────────────────────────
	const ytStats = $derived(stats?.by_type['youtube'] ?? null);
	const ytAvg = $derived(ytStats && ytStats.count > 0 ? Math.round(ytStats.minutes / ytStats.count) : 0);
	const ytPct = $derived(ytStats && stats ? Math.round(ytStats.minutes / stats.total_consumed_minutes * 100) : 0);
	const maxMovieMinutes = $derived(
		stats?.top_items_by_type['movie']?.length ? Math.max(...stats.top_items_by_type['movie'].map(m => m.minutes)) : 0
	);

	const maxYtGenreMinutes = $derived(
		stats?.top_youtube_genres?.length ? Math.max(1, ...stats.top_youtube_genres.map(g => g.minutes)) : 1
	);

	const peakHour = $derived.by(() => {
		if (!stats?.by_hour?.length) return null;
		return stats.by_hour.indexOf(Math.max(...stats.by_hour));
	});

	const timeProfile = $derived.by(() => {
		if (!stats?.by_hour?.length) return null;
		const h = stats.by_hour;
		const total = h.reduce((a, b) => a + b, 0) || 1;
		const night   = [...h.slice(21), ...h.slice(0, 4)].reduce((a, b) => a + b, 0);
		const morning = h.slice(6, 12).reduce((a, b) => a + b, 0);
		const evening = h.slice(18, 21).reduce((a, b) => a + b, 0);
		const afternoon = h.slice(12, 18).reduce((a, b) => a + b, 0);
		const max = Math.max(night, morning, evening, afternoon);
		if (max === night)   return { label: 'Búho nocturno',     sub: `El ${Math.round(night/total*100)}% de tu consumo es entre las 21h y las 4h` };
		if (max === morning) return { label: 'Madrugador',        sub: `El ${Math.round(morning/total*100)}% de tu consumo es por la mañana` };
		if (max === evening) return { label: 'Fan del prime time', sub: `El ${Math.round(evening/total*100)}% de tu consumo es entre las 18h y las 21h` };
		return { label: 'Tarde libre', sub: `El ${Math.round(afternoon/total*100)}% de tu consumo es por la tarde` };
	});

	const epicDay = $derived.by(() => {
		if (!stats?.calendar) return null;
		let best = { date: '', minutes: 0, count: 0 };
		for (const [date, d] of Object.entries(stats.calendar)) {
			if (d.minutes > best.minutes) best = { date, minutes: d.minutes, count: d.count };
		}
		return best.minutes > 0 ? best : null;
	});

	const REFS = [
		{ label: 'la trilogía de El Señor de los Anillos (extendida)', minutes: 690 },
		{ label: 'la saga completa de Star Wars (9 películas)', minutes: 1340 },
		{ label: 'todas las temporadas de Friends', minutes: 5400 },
		{ label: 'Elden Ring de principio a fin', minutes: 1680 },
	];
	const equivalences = $derived.by(() => {
		if (!stats) return [];
		return REFS.map(r => ({ ...r, times: +(stats!.total_consumed_minutes / r.minutes).toFixed(1) }))
			.filter(r => r.times >= 0.5);
	});

	// Logros (icon = nombre de Icon, no emoji)
	type Milestone = { icon: string; tt: string; ss: string; color: string };
	const milestones = $derived.by((): Milestone[] => {
		if (!stats) return [];
		const ms: Milestone[] = [];
		if (stats.streak_max >= 7)
			ms.push({ icon: 'flame', tt: `Racha de ${stats.streak_max} días`, ss: 'Sin parar ni un día', color: 'oklch(0.78 0.18 50)' });
		if (stats.total_consumed_count >= 100)
			ms.push({ icon: 'award', tt: '100+ ítems', ss: `Este año: ${stats.total_consumed_count}`, color: 'var(--primary)' });
		else if (stats.total_consumed_count >= 50)
			ms.push({ icon: 'award', tt: '50+ ítems', ss: `Este año: ${stats.total_consumed_count}`, color: 'var(--primary)' });
		if (stats.total_consumed_minutes >= 60 * 24 * 7)
			ms.push({ icon: 'calendar', tt: `${Math.floor(stats.total_consumed_minutes / (60*24))} días de contenido`, ss: 'Acumulados en el año', color: 'oklch(0.74 0.14 280)' });
		if (stats.completion_rate !== null && stats.completion_rate >= 85)
			ms.push({ icon: 'check', tt: `${stats.completion_rate}% completado`, ss: 'Casi nada se te resiste', color: 'oklch(0.76 0.18 150)' });
		if (stats.streaming_breakdown.length >= 3)
			ms.push({ icon: 'tv', tt: `${stats.streaming_breakdown.length} plataformas`, ss: stats.streaming_breakdown.map(p => p.name).join(', '), color: 'oklch(0.74 0.16 210)' });
		if ((stats.by_type['youtube']?.count ?? 0) >= 50)
			ms.push({ icon: 'play', tt: '50+ vídeos', ss: `Este año: ${stats.by_type['youtube'].count}`, color: 'var(--youtube)' });
		if ((stats.by_type['book']?.count ?? 0) >= 10)
			ms.push({ icon: 'book', tt: '10+ libros', ss: `Este año: ${stats.by_type['book'].count}`, color: 'var(--book)' });
		return ms;
	});

	// Stats por tipo (para las secciones de cada tipo)
	function typeAvg(type: string): number { const t = stats?.by_type[type]; return t && t.count > 0 ? Math.round(t.minutes / t.count) : 0; }
	function typePct(type: string): number { const t = stats?.by_type[type]; return t && stats ? Math.round(t.minutes / stats.total_consumed_minutes * 100) : 0; }
	// Artistas de música (campo opcional del backend; si no existe, la sub-sección se oculta)
	const musicArtists = $derived((((stats as unknown as { top_music_artists?: { name: string; count: number; minutes: number }[] })?.top_music_artists) ?? []));

	const ITEMS_PAGE = 12;

	// Game timeline — juegos consumidos en el año con su fecha de añadido y completado
	const gameTimeline = $derived(
		stats ? stats.items
			.filter(c => c.content_type === 'game' && c.consumed_at)
			.sort((a, b) => new Date(a.consumed_at!).getTime() - new Date(b.consumed_at!).getTime())
		: []
	);

	function dateToPct(dateStr: string, yr: number): number {
		const d = new Date(dateStr.length === 10 ? dateStr + 'T12:00:00' : dateStr);
		const start = new Date(yr, 0, 1).getTime();
		const end = new Date(yr + 1, 0, 1).getTime();
		return Math.min(100, Math.max(0, (d.getTime() - start) / (end - start) * 100));
	}
</script>

{#if !auth.isLoggedIn}
	<p class="muted center">Redirigiendo…</p>
{:else}

<!-- Topbar -->
<div class="desk-topbar desk-only">
	<h1 class="desk-title">Rewind {year}</h1>
	<div class="desk-spacer"></div>
	<button class="btn" onclick={() => year--}>‹ Anterior</button>
	<button class="btn" onclick={() => year++} disabled={year >= new Date().getFullYear()}>Siguiente ›</button>
</div>
<div class="row mobile-only" style="justify-content:center; margin:8px 0 20px; gap:16px;">
	<button class="btn" onclick={() => year--}>‹</button>
	<span style="font-size:18px; font-weight:700; color:var(--primary); min-width:140px; text-align:center;">Rewind {year}</span>
	<button class="btn" onclick={() => year++} disabled={year >= new Date().getFullYear()}>›</button>
</div>

{#if loading}
	<p class="muted center" style="margin-top:3rem;">Calculando tu año…</p>

{:else if loadError}
	<div class="glass empty">
		<p>Error cargando Rewind</p>
		<p class="muted" style="font-size:13px; margin-top:6px;">{loadError}</p>
	</div>

{:else if !stats || stats.total_consumed_count === 0}
	<div class="glass empty">
		<p>Sin contenido consumido en {year}.</p>
		<p class="muted" style="font-size:13px; margin-top:6px;">Marca ítems como consumidos para verlos aquí.</p>
	</div>

{:else}

<!-- ─── HERO ─── -->
<div class="surface rw-hero">
	<div class="rw-hero-main">
		<div class="rw-hero-kicker">Tu año en contenido</div>
		<div class="rw-hero-num">{formatDuration(stats.total_consumed_minutes)}</div>
		<div class="rw-hero-unit">{stats.total_consumed_count} ítems consumidos · ≈ {minutesToDays(stats.total_consumed_minutes)} de tu vida</div>
		<div class="rw-hero-sub">
			{#if stats.best_month !== null}{MONTHS_ES[(stats.best_month ?? 1) - 1]} fue tu mes récord{/if}
			{#if stats.favorite_type} · favorito: {TYPE_LABELS[stats.favorite_type] ?? stats.favorite_type}{/if}
		</div>
	</div>
	<div class="rw-hero-pct">
		<div class="rw-pct-num">{stats.percentage_of_year.toFixed(2)}%</div>
		<div class="rw-pct-lbl">de todo {year} dedicado a contenido</div>
		<div class="rw-pct-bar"><div class="rw-pct-fill" style="width:{Math.min(stats.percentage_of_year * 8, 100)}%"></div></div>
		<div class="rw-pct-scale"><span>0%</span><span>el año tiene 8.760h</span></div>
	</div>
</div>

<!-- ─── ESTATS ─── -->
<div class="surface estats-row">
	<div class="estat2"><div class="e-ic"><Icon name="flame" size={20} /></div><div class="e-v">{stats.streak_max}</div><div class="e-l">racha máx</div></div>
	{#if stats.best_month !== null}
		<div class="estat2"><div class="e-ic"><Icon name="calendar" size={20} /></div><div class="e-v">{MONTHS_ES[(stats.best_month ?? 1) - 1]}</div><div class="e-l">mejor mes</div></div>
	{/if}
	{#if stats.favorite_type}
		<div class="estat2"><div class="e-ic"><Icon name={TYPE_ICON[stats.favorite_type] ?? 'list'} size={20} /></div><div class="e-v">{TYPE_LABELS[stats.favorite_type] ?? stats.favorite_type}</div><div class="e-l">favorito</div></div>
	{/if}
	{#if stats.avg_rating != null}
		<div class="estat2"><div class="e-ic"><Icon name="star" size={20} /></div><div class="e-v">{stats.avg_rating}</div><div class="e-l">nota media</div></div>
	{/if}
	{#if stats.completion_rate !== null}
		<div class="estat2"><div class="e-ic"><Icon name="check" size={20} /></div><div class="e-v">{stats.completion_rate}%</div><div class="e-l">completado</div></div>
	{/if}
	{#if stats.abandoned_count > 0}
		<div class="estat2"><div class="e-ic"><Icon name="ban" size={20} /></div><div class="e-v">{stats.abandoned_count}</div><div class="e-l">abandonados</div></div>
	{/if}
</div>

<Chapter id="tiempo" label="TU AÑO EN EL TIEMPO" icon="calendar">

<div class="surface time-surface">
	<!-- Por mes -->
	<div class="tcell">
		<div class="panel-title"><Icon name="barChart" size={16} /> Por mes{#if topMonthIdx >= 0} · {MONTHS_ES[topMonthIdx]} fue el pico{/if}</div>
		<div class="month-bars2">
			{#each stats.by_month as m, i}
				{@const pct = Math.max(m.minutes / maxMonthMinutes * 100, m.minutes > 0 ? 4 : 0)}
				<div class="mb2-col" class:top={i === topMonthIdx}>
					<div class="mb2-val">{formatDuration(m.minutes)}</div>
					<div class="mb2-bar" class:top={i === topMonthIdx} style="height:{pct}%"></div>
					<div class="mb2-lbl">{MONTHS_ES[i]}</div>
				</div>
			{/each}
		</div>
	</div>
	<!-- Actividad diaria -->
	<div class="tcell">
		<div class="panel-title"><Icon name="activity" size={16} /> Actividad diaria</div>
		<div class="heatwrap">
			<div style="grid-template-columns: 18px repeat({calendarGrid.length}, 11px); display:grid; gap:2px; margin-bottom:3px;">
				<div></div>
				{#each calendarGrid as _, col}
					{@const label = calMonthLabels.find(m => m.col === col)}
					<div style="font-size:8px; color:var(--text-muted);">{label ? label.label : ''}</div>
				{/each}
			</div>
			<div style="display:flex; gap:4px;">
				<div style="display:flex; flex-direction:column; gap:2px;">
					{#each DAYS_ES as d, i}
						<div style="height:9px; font-size:7px; color:var(--text-muted); line-height:9px;">{i % 2 === 0 ? d : ''}</div>
					{/each}
				</div>
				<div style="display:flex; gap:2px;">
					{#each calendarGrid as week}
						<div style="display:flex; flex-direction:column; gap:2px;">
							{#each week as day}
								<div class="heat {heatLevel(day.minutes, day.inYear)}"
									style="width:9px; height:9px;{!day.inYear ? 'background:transparent; border-color:transparent;' : ''}"
									title={day.inYear && day.count > 0 ? `${day.key}: ${day.count} ítem${day.count !== 1 ? 's' : ''} · ${formatDuration(day.minutes)}` : day.key}
								></div>
							{/each}
						</div>
					{/each}
				</div>
			</div>
			<div class="heat-foot">
				<span>menos</span>
				<div class="heat" style="width:9px;height:9px;"></div>
				<div class="heat l1" style="width:9px;height:9px;"></div>
				<div class="heat l2" style="width:9px;height:9px;"></div>
				<div class="heat l3" style="width:9px;height:9px;"></div>
				<div class="heat l4" style="width:9px;height:9px;"></div>
				<span>más</span>
			</div>
		</div>
	</div>
	<!-- Por hora -->
	{#if stats.by_hour?.length === 24}
		<div class="tcell">
			<div class="panel-title"><Icon name="clock" size={16} /> Por hora del día{#if peakHour !== null} · pico a las {peakHour}h{/if}</div>
			<div class="whour-blocks">
				{#each stats.by_hour as v, i}
					{@const intensity = v / maxHour}
					{@const alpha = 0.07 + intensity * 0.85}
					<div class="whour-block"
						style="background:oklch(0.65 0.22 290 / {alpha});{intensity > 0.7 ? 'box-shadow:0 0 6px oklch(0.65 0.22 290/0.4)' : ''}"
						title="{i}h · {formatDuration(v)}"></div>
				{/each}
			</div>
			<div class="whour-labels"><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span></div>
		</div>
	{/if}
	<!-- Por día -->
	{#if stats.by_day?.length}
		<div class="tcell">
			<div class="panel-title"><Icon name="barChart" size={16} /> Por día{#if topDayIdx >= 0} · {DAYS_FULL[topDayIdx]} es tu día{/if}</div>
			<div class="day-bars">
				{#each stats.by_day as v, i}
					{@const pct = Math.max(v / maxDay * 100, 4)}
					<div class="db-col"><div class="db-bar" class:top={i === topDayIdx} style="height:{pct}%" title={formatDuration(v)}></div><div class="db-lbl">{DAYS_ES[i]}</div></div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<!-- Momento + día épico -->
<div class="surface moment-surface">
	{#if stats.moment}
		<div class="moment-card">
			<div class="moment-icon"><Icon name="zap" size={24} /></div>
			<div class="moment-body">
				<div class="moment-kicker">Tu mejor semana</div>
				<div class="moment-title">{new Date(stats.moment.week_start + 'T12:00:00').toLocaleDateString('es', {day:'numeric', month:'long'})} – {new Date(stats.moment.week_end + 'T12:00:00').toLocaleDateString('es', {day:'numeric', month:'long'})}</div>
				<div class="moment-sub">{stats.moment.count} ítem{stats.moment.count !== 1 ? 's' : ''} en 7 días</div>
			</div>
			<div class="moment-stat"><div class="moment-val">{formatDuration(stats.moment.minutes)}</div><div class="moment-lbl">esa semana</div></div>
		</div>
	{/if}
	{#if epicDay}
		<div class="moment-card">
			<div class="moment-icon warm"><Icon name="mountain" size={24} /></div>
			<div class="moment-body">
				<div class="moment-kicker">Tu día más épico</div>
				<div class="moment-title">{new Date(epicDay.date + 'T12:00:00').toLocaleDateString('es', { weekday:'long', day:'numeric', month:'long' })}</div>
				<div class="moment-sub">{stats.epic_day_items.slice(0,2).map(i => i.title).join(' · ')}{stats.epic_day_items.length > 2 ? '…' : ''}</div>
			</div>
			<div class="moment-stat"><div class="moment-val warm">{formatDuration(epicDay.minutes)}</div><div class="moment-lbl">en un día</div></div>
		</div>
	{/if}
</div>

</Chapter>

{#if typeSorted.length > 0}
<Chapter id="reparto" label="EN QUÉ SE TE VA EL TIEMPO" icon="layers">
	<div class="surface type-overview">
		<div class="div-bar">
			{#each typeSorted as [type, s]}<div class="div-seg" style="flex:{s.minutes}; background:{TYPE_COLORS[type] ?? 'var(--primary)'}"></div>{/each}
		</div>
		<div class="to-legend">
			{#each typeSorted as [type, s]}
				<div class="to-item"><span class="to-dot" style="background:{TYPE_COLORS[type] ?? 'var(--primary)'}"></span><span class="to-ic"><Icon name={TYPE_ICON[type] ?? 'list'} size={14} /></span><span class="to-nm">{TYPE_LABELS[type] ?? type}</span><span class="to-pct">{Math.round(s.minutes / typeTotal * 100)}%</span></div>
			{/each}
		</div>
	</div>
</Chapter>
{/if}

<!-- ─── YOUTUBE ─── -->
{#if stats.top_youtube_channels.length > 0}
	{@const topCh = stats.top_youtube_channels[0]}
	<Chapter id="youtube" label="YOUTUBE" icon="play">

	<!-- Hero de creador -->
	<div class="surface yt-hero">
		{#if topCh.thumbnail}
			<img class="yt-creator-avatar" style="--yt-glow:{channelColor(topCh.name)}" src={topCh.thumbnail} alt={topCh.name} />
		{:else}
			<div class="yt-creator-avatar yt-creator-ph" style="--yt-glow:{channelColor(topCh.name)}; background:{channelColor(topCh.name)}">{topCh.name[0]?.toUpperCase() ?? '?'}</div>
		{/if}
		<div class="yt-creator-body">
			<div class="yt-kicker"><Icon name="play" size={12} /> Tu creador del año</div>
			<div class="yt-name">{topCh.name}</div>
			<div class="yt-stat-line">{topCh.count} vídeo{topCh.count !== 1 ? 's' : ''} · {formatDuration(topCh.minutes)}</div>
			<div class="yt-hook">
				{#if maxMovieMinutes > 0}
					Le dedicaste más horas que a cualquier película de tu año — la más larga apenas duró {formatDuration(maxMovieMinutes)}.
				{:else}
					{formatDuration(topCh.minutes)} con una sola persona a lo largo del año.
				{/if}
			</div>
		</div>
		{#if stats.top_youtube_channels.length > 1}
			<div class="yt-runners">
				{#each stats.top_youtube_channels.slice(1, 3) as c, i}
					<div class="yt-runner">
						<span class="yt-runner-rank">#{i + 2}</span>
						{#if c.thumbnail}
							<img class="yt-runner-av" src={c.thumbnail} alt={c.name} />
						{:else}
							<div class="yt-runner-av" style="display:grid; place-items:center; font-weight:800; color:#fff;">{c.name[0]?.toUpperCase() ?? '?'}</div>
						{/if}
						<div class="yt-runner-info"><div class="yt-runner-name">{c.name}</div><div class="yt-runner-time">{formatDuration(c.minutes)}</div></div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Mini-stats solo YouTube -->
	{#if ytStats}
		<div class="surface yt-stats">
			<div class="estat2"><div class="e-ic"><Icon name="play" size={20} /></div><div class="e-v">{ytStats.count}</div><div class="e-l">vídeos</div></div>
			<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(ytStats.minutes)}</div><div class="e-l">en total</div></div>
			<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(ytAvg)}</div><div class="e-l">media/vídeo</div></div>
			<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{ytPct}%</div><div class="e-l">de tu consumo</div></div>
		</div>
	{/if}

	<!-- Categorías de YouTube -->
	{#if (stats.top_youtube_genres?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="layers" size={15} /></span> Qué tipo de contenido</h2>
			<div class="surface yt-genres">
				{#each stats.top_youtube_genres as g}
					{@const pct = Math.round(g.minutes / maxYtGenreMinutes * 100)}
					<div class="ytg-row">
						<div class="ytg-name">{g.genre}</div>
						<div class="ytg-bar-wrap">
							<div class="ytg-bar" style="width:{pct}%"></div>
						</div>
						<div class="ytg-meta">{g.count} vídeo{g.count !== 1 ? 's' : ''} · {formatDuration(g.minutes)}</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Canales más vistos -->
	<section class="rewind-section">
		<h2><span class="hico"><Icon name="play" size={15} /></span> Canales más vistos</h2>
		<div class="channels-dual">
			<div class="channels-col">
				<div class="channels-col-head"><Icon name="clock" size={13} /> Por tiempo</div>
				<div class="surface channel-grid">
					{#each stats.top_youtube_channels as ch, i}
						<div class="channel-card" style="--ch-color:{channelColor(ch.name)}">
							<div class="ch-rank">#{i + 1}</div>
							{#if ch.thumbnail}<img class="ch-avatar" src={ch.thumbnail} alt={ch.name} />{:else}<div class="ch-avatar">{ch.name[0]?.toUpperCase() ?? '?'}</div>{/if}
							<div class="ch-info"><div class="ch-name">{ch.name}</div><div class="ch-meta">{ch.count} vídeo{ch.count !== 1 ? 's' : ''}</div></div>
							<div class="ch-time">{formatDuration(ch.minutes)}</div>
						</div>
					{/each}
				</div>
			</div>
			<div class="channels-col">
				<div class="channels-col-head"><Icon name="list" size={13} /> Por nº de vídeos</div>
				<div class="surface channel-grid">
					{#each stats.top_youtube_channels_by_count as ch, i}
						<div class="channel-card" style="--ch-color:{channelColor(ch.name)}">
							<div class="ch-rank">#{i + 1}</div>
							{#if ch.thumbnail}<img class="ch-avatar" src={ch.thumbnail} alt={ch.name} />{:else}<div class="ch-avatar">{ch.name[0]?.toUpperCase() ?? '?'}</div>{/if}
							<div class="ch-info"><div class="ch-name">{ch.name}</div><div class="ch-meta">{formatDuration(ch.minutes)} totales</div></div>
							<div class="ch-time">{ch.count} vídeos</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</section>

	<!-- Vídeos más largos -->
	{#if (stats.top_items_by_type['youtube']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="play" size={15} /></span> Vídeos más largos</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['youtube'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--youtube)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img land" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img land ph"><Icon name="play" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
	</Chapter>
{/if}

<!-- ─── SECCIONES POR TIPO ─── -->
{#if stats.by_type['series']}
<Chapter id="series" label="SERIES" icon="tv">
	{#if (stats.top_items_by_type['series']?.length ?? 0) > 0}
		{@const top = stats.top_items_by_type['series'][0]}
		<div class="tb-hook">Maratoneaste <strong>{top.title}</strong> — {formatDuration(top.minutes)} tú solo.</div>
	{/if}
	<div class="surface kpi-strip" style="--accent:var(--series)">
		<div class="estat2"><div class="e-ic"><Icon name="tv" size={20} /></div><div class="e-v">{stats.by_type['series'].count}</div><div class="e-l">series</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(stats.by_type['series'].minutes)}</div><div class="e-l">en total</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(typeAvg('series'))}</div><div class="e-l">media/u</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{typePct('series')}%</div><div class="e-l">de tu consumo</div></div>
	</div>
	{#if (stats.top_items_by_type['series']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="tv" size={15} /></span> Series más largas</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['series'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--series)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img land" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img land ph"><Icon name="tv" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
	{#if stats.streaming_breakdown.length > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="film" size={15} /></span> Plataformas de streaming</h2>
			<div class="surface streaming-grid" style="grid-template-columns:repeat({stats.streaming_breakdown.length}, 1fr)">
				{#each stats.streaming_breakdown as plat, i}
					{@const ppct = Math.round(plat.minutes / maxStreamingMins * 100)}
					{@const pc = PLATFORM_COLORS[plat.name] ?? 'var(--movie)'}
					{@const avgMin = plat.count > 0 ? Math.round(plat.minutes / plat.count) : 0}
					<div class="plat-card" style="--pc:{pc}">
						<div class="plat-header"><span class="plat-name">{plat.name}</span><span class="plat-rank">#{i + 1}</span></div>
						<div class="plat-time">{formatDuration(plat.minutes)}</div>
						<div class="plat-bar-wrap"><div class="plat-bar" style="width:{ppct}%;"></div></div>
						<div class="plat-footer"><span class="plat-count">{plat.count} título{plat.count !== 1 ? 's' : ''}</span>{#if avgMin > 0}<span class="plat-avg">~{formatDuration(avgMin)}/u</span>{/if}</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</Chapter>
{/if}

{#if stats.by_type['game']}
<Chapter id="game" label="JUEGOS" icon="game">
	{#if (stats.top_items_by_type['game']?.length ?? 0) > 0}
		{@const top = stats.top_items_by_type['game'][0]}
		<div class="tb-hook"><strong>{top.title}</strong> se llevó {formatDuration(top.minutes)} de tu año.</div>
	{/if}
	<div class="surface kpi-strip" style="--accent:var(--game)">
		<div class="estat2"><div class="e-ic"><Icon name="game" size={20} /></div><div class="e-v">{stats.by_type['game'].count}</div><div class="e-l">juegos</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(stats.by_type['game'].minutes)}</div><div class="e-l">en total</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(typeAvg('game'))}</div><div class="e-l">media/u</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{typePct('game')}%</div><div class="e-l">de tu consumo</div></div>
	</div>
	{#if gameTimeline.length > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="activity" size={15} /></span> Línea de tiempo</h2>
			<div class="surface gtl-surface">
				<div class="gtl-header">
					<div></div>
					<div class="gtl-months">
						{#each MONTHS_ES as m}<span>{m}</span>{/each}
					</div>
				</div>
				<div class="gtl-rows">
					{#each gameTimeline as game}
						{@const addPct    = dateToPct(game.created_at, year)}
						{@const donePct   = dateToPct(game.consumed_at!, year)}
						{@const addedBefore = new Date(game.created_at.length === 10 ? game.created_at + 'T12:00:00' : game.created_at).getFullYear() < year}
						{@const barLeft   = addedBefore ? 0 : addPct}
						{@const barWidth  = Math.max(0, donePct - barLeft)}
						<div class="gtl-row">
							<div class="gtl-info">
								{#if game.thumbnail}
									<img class="gtl-thumb" src={game.thumbnail} alt="" />
								{:else}
									<div class="gtl-thumb-ph"><Icon name="game" size={10} /></div>
								{/if}
								<span class="gtl-title">{game.title}</span>
							</div>
							<div class="gtl-track">
								<div class="gtl-baseline"></div>
								{#if barWidth > 0.5}
									<div class="gtl-bar" class:before={addedBefore}
										style="left:{barLeft}%; width:{barWidth}%"
										title={addedBefore ? `En backlog desde antes de ${year}` : `Añadido: ${game.created_at.slice(0,10)}`}
									></div>
								{/if}
								{#if !addedBefore && Math.abs(donePct - addPct) > 0.5}
									<div class="gtl-dot add" style="left:{addPct}%"
										title={`Añadido: ${new Date(game.created_at.length === 10 ? game.created_at + 'T12:00:00' : game.created_at).toLocaleDateString('es', {day:'numeric', month:'short', year:'numeric'})}`}
									></div>
								{/if}
								<div class="gtl-dot done" style="left:{donePct}%"
									title={`Completado: ${new Date(game.consumed_at!.length === 10 ? game.consumed_at! + 'T12:00:00' : game.consumed_at!).toLocaleDateString('es', {day:'numeric', month:'short'})}`}
								></div>
							</div>
						</div>
					{/each}
				</div>
				<div class="gtl-legend">
					<span class="gtl-leg-item"><span class="gtl-leg-dot add"></span>Añadido al vault</span>
					<span class="gtl-leg-item"><span class="gtl-leg-dot done"></span>Completado</span>
					<span class="gtl-leg-item"><span class="gtl-leg-line-dash"></span>Desde backlog anterior</span>
				</div>
			</div>
		</section>
	{/if}

	{#if (stats.top_items_by_type['game']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="game" size={15} /></span> Juegos más largos</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['game'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--game)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img land" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img land ph"><Icon name="game" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}

</Chapter>
{/if}

{#if stats.by_type['movie']}
<Chapter id="movie" label="PELÍCULAS" icon="film">
	{#if (stats.top_items_by_type['movie']?.length ?? 0) > 0}
		{@const top = stats.top_items_by_type['movie'][0]}
		<div class="tb-hook">Tu sesión más larga fue <strong>{top.title}</strong> ({formatDuration(top.minutes)}).</div>
	{/if}
	<div class="surface kpi-strip" style="--accent:var(--movie)">
		<div class="estat2"><div class="e-ic"><Icon name="film" size={20} /></div><div class="e-v">{stats.by_type['movie'].count}</div><div class="e-l">películas</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(stats.by_type['movie'].minutes)}</div><div class="e-l">en total</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(typeAvg('movie'))}</div><div class="e-l">media/u</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{typePct('movie')}%</div><div class="e-l">de tu consumo</div></div>
	</div>
	{#if (stats.top_items_by_type['movie']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="film" size={15} /></span> Películas más largas</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['movie'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--movie)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img land" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img land ph"><Icon name="film" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}

</Chapter>
{/if}

{#if stats.by_type['book']}
<Chapter id="book" label="LIBROS" icon="book">
	{#if (stats.top_items_by_type['book']?.length ?? 0) > 0}
		{@const top = stats.top_items_by_type['book'][0]}
		<div class="tb-hook">{#if stats.top_book_authors.length > 0}<strong>{stats.top_book_authors[0].name}</strong> fue tu autor más leído.{/if}</div>
	{/if}
	<div class="surface kpi-strip" style="--accent:var(--book)">
		<div class="estat2"><div class="e-ic"><Icon name="book" size={20} /></div><div class="e-v">{stats.by_type['book'].count}</div><div class="e-l">libros</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(stats.by_type['book'].minutes)}</div><div class="e-l">en total</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(typeAvg('book'))}</div><div class="e-l">media/u</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{typePct('book')}%</div><div class="e-l">de tu consumo</div></div>
	</div>
	{#if stats.top_book_authors.length > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="book" size={15} /></span> Autores más leídos</h2>
			<div class="surface channel-grid channel-grid-multi">
				{#each stats.top_book_authors as author, i}
					<div class="channel-card" style="--ch-color:var(--book)">
						<div class="ch-rank">#{i + 1}</div>
						<div class="ch-avatar" style="background:var(--book)">{author.name[0]?.toUpperCase() ?? '?'}</div>
						<div class="ch-info"><div class="ch-name">{author.name}</div><div class="ch-meta">{author.count} libro{author.count !== 1 ? 's' : ''}</div></div>
						<div class="ch-time" style="color:var(--book)">{formatDuration(author.minutes)}</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
	{#if (stats.top_items_by_type['book']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="book" size={15} /></span> Libros más largos</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['book'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--book)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img port" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img port ph"><Icon name="book" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</Chapter>
{/if}

{#if stats.by_type['music']}
<Chapter id="music" label="MÚSICA" icon="music">
	{#if musicArtists.length > 0}
		<div class="tb-hook"><strong>{musicArtists[0].name}</strong> sonó más que nadie.</div>
	{/if}
	<div class="surface kpi-strip" style="--accent:var(--music)">
		<div class="estat2"><div class="e-ic"><Icon name="music" size={20} /></div><div class="e-v">{stats.by_type['music'].count}</div><div class="e-l">temas</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="clock" size={20} /></div><div class="e-v">{formatDuration(stats.by_type['music'].minutes)}</div><div class="e-l">en total</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="activity" size={20} /></div><div class="e-v">{formatDuration(typeAvg('music'))}</div><div class="e-l">media/u</div></div>
		<div class="estat2"><div class="e-ic"><Icon name="percent" size={20} /></div><div class="e-v">{typePct('music')}%</div><div class="e-l">de tu consumo</div></div>
	</div>
	{#if musicArtists.length > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="music" size={15} /></span> Artistas más escuchados</h2>
			<div class="surface channel-grid channel-grid-multi">
				{#each musicArtists as artist, i}
					<div class="channel-card" style="--ch-color:var(--music)">
						<div class="ch-rank">#{i + 1}</div>
						<div class="ch-avatar" style="background:var(--music)">{artist.name[0]?.toUpperCase() ?? '?'}</div>
						<div class="ch-info"><div class="ch-name">{artist.name}</div><div class="ch-meta">{artist.count} tema{artist.count !== 1 ? 's' : ''}</div></div>
						<div class="ch-time" style="color:var(--music)">{formatDuration(artist.minutes)}</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
	{#if (stats.top_items_by_type['music']?.length ?? 0) > 0}
		<section class="rewind-section">
			<h2><span class="hico"><Icon name="music" size={15} /></span> Más escuchado</h2>
			<div class="surface podium-grid">
				{#each (stats.top_items_by_type['music'] ?? []) as item, i}
					<div class="podium-card" style="--accent:var(--music)">
						<div class="podium-no">{i + 1}</div>
						{#if item.thumbnail}<img class="podium-img port" src={item.thumbnail} alt="" loading="lazy" />{:else}<div class="podium-img port ph"><Icon name="music" size={20} /></div>{/if}
						<div class="podium-body"><div class="podium-title">{item.title}</div>{#if item.author}<div class="podium-sub">{item.author}</div>{/if}<div class="podium-badge">{formatDuration(item.minutes)}</div></div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</Chapter>
{/if}

<!-- ─── TU PERFIL ─── -->
<Chapter id="perfil" label="TU PERFIL" icon="sparkles">
<div class="surface profile-grid">
	<!-- Racha -->
	{#if stats.streak_max > 0}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,oklch(0.82 0.18 85 / 0.8),transparent)"></div>
			<div class="streak-flame"><Icon name="flame" size={90} /></div>
			<div class="pcard-kicker"><Icon name="flame" size={12} /> Racha más larga</div>
			<div class="streak-num">{stats.streak_max}</div>
			<div style="font-size:15px; font-weight:700; color:var(--text-muted)">días seguidos</div>
			{#if stats.streak_current > 0}<div class="pcard-sub">Racha actual: {stats.streak_current} días</div>{/if}
		</div>
	{/if}
	<!-- Patrón -->
	{#if timeProfile}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,oklch(0.68 0.18 240 / 0.7),transparent)"></div>
			<div class="pcard-kicker"><Icon name="clock" size={12} /> Tu patrón</div>
			<div class="pcard-big" style="font-size:28px">{timeProfile.label}</div>
			<div class="pcard-sub">{timeProfile.sub}</div>
			<div class="day-pills">
				{#each DAYS_ES as d, i}
					<div class="day-pill" class:active={(stats.by_day?.[i] ?? 0) >= maxDay * 0.7}>{d}</div>
				{/each}
			</div>
		</div>
	{/if}
	<!-- Comparativa anual -->
	{#if (stats.prev_year_minutes ?? 0) > 0}
		{@const cur = stats.total_consumed_minutes}
		{@const prev = stats.prev_year_minutes}
		{@const mx = Math.max(cur, prev, 1)}
		{@const delta = Math.round((cur - prev) / prev * 100)}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,var(--primary),transparent)"></div>
			<div class="pcard-kicker"><Icon name="trendingUp" size={12} /> vs {year - 1}</div>
			<div class="cmp-row"><span class="cmp-year" style="color:var(--primary); font-weight:800">{year}</span><div class="cmp-track"><div class="cmp-fill" style="width:{cur/mx*100}%; background:var(--primary)"></div></div><span class="cmp-val" style="color:var(--primary)">{formatDuration(cur)}</span></div>
			<div class="cmp-row"><span class="cmp-year">{year - 1}</span><div class="cmp-track"><div class="cmp-fill" style="width:{prev/mx*100}%; background:rgba(255,255,255,0.2)"></div></div><span class="cmp-val">{formatDuration(prev)}</span></div>
			<div class="cmp-delta" class:up={delta >= 0} class:down={delta < 0}><Icon name="trendingUp" size={12} /> {delta >= 0 ? '+' : ''}{delta}% vs {year - 1}</div>
		</div>
	{/if}
	<!-- Equivalencias -->
	{#if equivalences.length > 0}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,oklch(0.82 0.18 85 / 0.7),transparent)"></div>
			<div class="pcard-kicker"><Icon name="sparkles" size={12} /> En perspectiva</div>
			{#each equivalences.slice(0, 3) as eq}
				<div class="equiv-row"><span class="equiv-times">{eq.times}×</span><span class="equiv-label">{eq.label}</span></div>
			{/each}
		</div>
	{/if}
	<!-- Calidad -->
	{#if stats.avg_rating != null}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,oklch(0.82 0.18 85 / 0.7),transparent)"></div>
			<div class="pcard-kicker"><Icon name="star" size={12} /> Calidad media</div>
			<div style="display:flex; align-items:baseline; gap:6px;"><span class="pcard-big" style="color:oklch(0.84 0.16 85)">{stats.avg_rating}</span><span style="font-size:16px; color:var(--text-dim)">/10</span></div>
			{#if stats.best_rated_item}<div class="rating-row"><span class="rating-star" style="color:oklch(0.84 0.16 85)"><Icon name="star" size={12} /> {stats.best_rated_item.rating}</span><span class="rating-title">{stats.best_rated_item.title}</span></div>{/if}
			{#if stats.worst_rated_item}<div class="rating-row"><span class="rating-star" style="color:oklch(0.66 0.2 25)"><Icon name="star" size={12} /> {stats.worst_rated_item.rating}</span><span class="rating-title" style="color:var(--text-dim)">{stats.worst_rated_item.title}</span></div>{/if}
		</div>
	{/if}
	<!-- Día épico al detalle -->
	{#if epicDay && stats.epic_day_items.length > 0}
		<div class="pcard">
			<div class="pcard-accent" style="background:linear-gradient(90deg,transparent,oklch(0.66 0.2 25 / 0.7),transparent)"></div>
			<div class="pcard-kicker"><Icon name="mountain" size={12} /> Tu día épico al detalle</div>
			<div class="pcard-big" style="font-size:30px; color:oklch(0.72 0.18 30)">{formatDuration(epicDay.minutes)}</div>
			<div class="epic-list">
				{#each stats.epic_day_items as it}
					<div class="epic-row"><Icon name={TYPE_ICON[it.content_type] ?? 'list'} size={14} /><span class="t">{it.title}</span>{#if it.duration_minutes > 0}<span class="epic-dur">{formatDuration(it.duration_minutes)}</span>{/if}</div>
				{/each}
			</div>
		</div>
	{/if}
</div>

<!-- Logros -->
{#if milestones.length > 0}
	<section class="rewind-section">
		<h2><span class="hico"><Icon name="award" size={15} /></span> Logros del año</h2>
		<div class="surface ms-grid" style="grid-template-columns:repeat({Math.min(milestones.length, 4)}, 1fr)">
			{#each milestones as m}
				<div class="ms-card" style="--ms-color:{m.color}">
					<div class="ms-ic"><Icon name={m.icon} size={22} /></div>
					<div class="ms-body"><div class="ms-title">{m.tt}</div><div class="ms-sub">{m.ss}</div></div>
				</div>
			{/each}
		</div>
	</section>
{/if}

</Chapter>

<!-- ─── COMPARTIR ─── -->
<Chapter id="compartir" label="COMPARTIR" icon="share">
<section class="rewind-section">
	<div class="share-card">
		<div class="share-head">
			<div class="share-brand"><div class="share-mark">⛧</div><div><div class="share-name">Deus Vault</div><div class="share-tagline">memento mori</div></div></div>
			<div class="share-yr">REWIND {stats.year}</div>
		</div>
		<div class="share-grid">
			<div class="share-block"><div class="share-lbl">Tu año</div><div class="share-val big">{formatDuration(stats.total_consumed_minutes)}</div><div class="share-sub">{stats.total_consumed_count} ítems</div></div>
			{#if stats.top_youtube_channels.length > 0}<div class="share-block"><div class="share-lbl">Top canal</div><div class="share-val">{stats.top_youtube_channels[0].name}</div><div class="share-sub">{formatDuration(stats.top_youtube_channels[0].minutes)}</div></div>{/if}
			{#if stats.top_items_by_type['series']?.length > 0}<div class="share-block"><div class="share-lbl">Top serie</div><div class="share-val">{stats.top_items_by_type['series'][0].title}</div><div class="share-sub">{formatDuration(stats.top_items_by_type['series'][0].minutes)}</div></div>{:else if stats.top_items_by_type['movie']?.length > 0}<div class="share-block"><div class="share-lbl">Top película</div><div class="share-val">{stats.top_items_by_type['movie'][0].title}</div><div class="share-sub">{formatDuration(stats.top_items_by_type['movie'][0].minutes)}</div></div>{/if}
			{#if stats.streak_max > 0}<div class="share-block"><div class="share-lbl">Racha máx.</div><div class="share-val">{stats.streak_max} días</div><div class="share-sub">sin parar</div></div>{/if}
		</div>
		<div class="share-actions">
			<button class="btn share-btn-primary" onclick={() => stats && exportShareImage(stats)}><Icon name="share" size={16} /> Descargar imagen</button>
		</div>
	</div>
</section>

</Chapter>

<!-- Quote -->
<div class="glass quote-card">
	<Icon name="sparkles" size={36} />
	<div>
		<div class="quote-text">En {year} consumiste <strong style="color:var(--primary)">{formatDuration(stats.total_consumed_minutes)}</strong> de contenido. Son <strong style="color:oklch(0.84 0.16 85)">{minutesToDays(stats.total_consumed_minutes)}</strong> de tu vida.</div>
		<div class="quote-sub">Memento mori — ¿valió la pena cada uno?</div>
	</div>
</div>

<!-- Todo lo consumido -->
{#if stats.items.length > 0}
	<section class="rewind-section">
		<h2><span class="hico"><Icon name="list" size={15} /></span> Todo lo consumido <span class="h2-count">({stats.items.length})</span></h2>
		<div class="content-grid">
			{#each stats.items.slice(0, itemsVisible) as c (c.id)}
				{@const landscape = c.content_type === 'youtube' || c.content_type === 'movie' || c.content_type === 'series' || c.content_type === 'game'}
				<div class="c-card" class:landscape class:portrait={!landscape} style="--card-accent:{TYPE_COLORS[c.content_type] ?? 'var(--primary)'}; --accent:{TYPE_COLORS[c.content_type] ?? 'var(--primary)'}">
					{#if landscape}
						<div class="thumb-land">{#if c.thumbnail}<img src={c.thumbnail} alt="" />{:else}<div class="ph"><Icon name={TYPE_ICON[c.content_type] ?? 'list'} size={28} /></div>{/if}</div>
					{:else}
						<div class="thumb-port">{#if c.thumbnail}<img src={c.thumbnail} alt="" />{:else}<div class="ph"><Icon name={TYPE_ICON[c.content_type] ?? 'list'} size={28} /></div>{/if}</div>
					{/if}
					<div class="info">
						<div class="title">{c.title}</div>
						<div class="meta">
							<span class="badge">{TYPE_LABELS[c.content_type]}</span>
							{#if c.duration_minutes > 0}<span>{formatDuration(c.duration_minutes)}</span>{/if}
							{#if c.author}<span>{c.author}</span>{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>
		{#if itemsVisible < stats.items.length}
			<div class="show-more">
				<button class="btn btn-lg" onclick={() => itemsVisible += ITEMS_PAGE}>Ver más ({stats.items.length - itemsVisible} restantes)</button>
			</div>
		{/if}
	</section>
{/if}

{/if}
{/if}

<style>
	/* Encabezados de sección */
	.rewind-section { margin-bottom: 20px; }
	.rewind-section h2 {
		font-size: 12px; font-weight: 800; text-transform: uppercase;
		letter-spacing: 0.18em; color: var(--text-muted); margin-bottom: 11px;
		display: flex; align-items: center; gap: 10px;
	}
	.rewind-section h2 .hico {
		width: 26px; height: 26px; border-radius: 8px; color: var(--primary);
		background: var(--glass-bg-strong); border: 1px solid var(--glass-border);
		display: grid; place-items: center; flex-shrink: 0;
	}
	.h2-count { font-size: 13px; color: var(--text-dim); font-weight: 500; letter-spacing: 0; text-transform: none; }

	.deep-divider { display: flex; align-items: center; gap: 16px; margin: 30px 0 20px; }
	.dd-line { flex: 1; height: 1px; background: linear-gradient(90deg, transparent, var(--glass-border), transparent); }
	.dd-label { font-size: 10px; font-weight: 900; letter-spacing: 0.26em; color: var(--text-dim); display: flex; align-items: center; gap: 8px; }
	.dd-label :global(svg) { color: var(--primary); opacity: 0.7; }

	/* Superficie unificada */
	.surface {
		position: relative; background: var(--glass-bg); border: 1px solid var(--glass-border);
		border-radius: 18px; box-shadow: var(--glass-shadow), var(--glass-inner);
		backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		-webkit-backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
		overflow: hidden; margin-bottom: 14px;
	}
	.surface::before { content: ''; position: absolute; top: 0; left: 8%; right: 8%; height: 1px; background: linear-gradient(90deg, transparent, var(--glass-shine), transparent); pointer-events: none; z-index: 2; }

	/* Hero */
	.rw-hero { display: grid; grid-template-columns: 1.35fr 1fr; }
	.rw-hero-main { padding: 24px 30px; display: flex; flex-direction: column; justify-content: center; }
	.rw-hero-kicker { font-size: 11px; font-weight: 800; letter-spacing: 0.28em; color: var(--text-muted); text-transform: uppercase; }
	.rw-hero-num { font-weight: 900; font-size: clamp(56px, 5.5vw, 92px); line-height: 0.9; letter-spacing: -0.04em; margin: 6px 0 5px;
		background: linear-gradient(165deg, #fff 25%, var(--primary)); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 28px oklch(0.78 0.15 300 / 0.35)); }
	.rw-hero-unit { font-size: 16px; font-weight: 600; color: var(--text); }
	.rw-hero-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
	.rw-hero-pct { padding: 20px 22px; display: flex; flex-direction: column; justify-content: center; border-left: 1px solid var(--glass-border); }
	.rw-pct-num { text-align: center; font-size: 48px; font-weight: 900; color: var(--primary); line-height: 1; letter-spacing: -0.04em; filter: drop-shadow(0 0 24px oklch(0.78 0.15 300 / 0.5)); }
	.rw-pct-lbl { text-align: center; font-size: 12px; color: var(--text-muted); margin-top: 6px; }
	.rw-pct-bar { height: 6px; border-radius: 99px; background: oklch(0.30 0.01 290 / 0.7); border: 1px solid oklch(0.50 0.02 290 / 0.2); overflow: hidden; margin: 14px 0 4px; }
	.rw-pct-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--primary), oklch(0.86 0.12 210)); }
	.rw-pct-scale { display: flex; justify-content: space-between; font-size: 9px; color: var(--text-dim); }

	/* Estats */
	.estats-row { display: grid; grid-template-columns: repeat(6, 1fr); margin-bottom: 20px; }
	.estat2 { padding: 14px 10px; text-align: center; }
	.estat2:not(:first-child) { border-left: 1px solid var(--glass-border); }
	.e-ic { color: var(--primary); opacity: 0.85; margin-bottom: 5px; display: flex; justify-content: center; }
	.e-v { font-size: 19px; font-weight: 900; line-height: 1; letter-spacing: -0.02em; }
	.e-l { font-size: 10px; color: var(--text-muted); margin-top: 5px; text-transform: uppercase; letter-spacing: 0.06em; }

	/* Zona YouTube */
	.yt-hero { display: flex; align-items: center; gap: 24px; padding: 22px 26px; }
	.yt-creator-avatar { width: 88px; height: 88px; border-radius: 50%; flex-shrink: 0; object-fit: cover;
		box-shadow: 0 0 0 2px var(--glass-border), 0 0 32px color-mix(in srgb, var(--yt-glow, var(--youtube)) 42%, transparent); }
	.yt-creator-ph { display: grid; place-items: center; font-size: 34px; font-weight: 900; color: #fff; }
	.yt-creator-body { flex: 1; min-width: 0; }
	.yt-kicker { font-size: 10px; font-weight: 800; letter-spacing: 0.16em; text-transform: uppercase; color: var(--text-muted); display: flex; align-items: center; gap: 7px; }
	.yt-kicker :global(svg) { color: var(--youtube); }
	.yt-name { font-size: 32px; font-weight: 900; letter-spacing: -0.02em; line-height: 1.05; margin: 5px 0 3px; }
	.yt-stat-line { font-size: 14px; font-weight: 800; color: var(--youtube); filter: brightness(1.25); }
	.yt-hook { font-size: 13px; color: var(--text-muted); margin-top: 7px; line-height: 1.45; max-width: 48ch; }
	.yt-runners { flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; border-left: 1px solid var(--glass-border); padding-left: 22px; }
	.yt-runner { display: flex; align-items: center; gap: 10px; }
	.yt-runner-rank { font-size: 11px; font-weight: 800; color: var(--text-dim); min-width: 18px; }
	.yt-runner-av { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: var(--youtube); }
	.yt-runner-info { min-width: 0; }
	.yt-runner-name { font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
	.yt-runner-time { font-size: 11px; color: var(--text-muted); }
	.yt-stats { display: grid; grid-template-columns: repeat(4, 1fr); }

	/* Géneros YouTube */
	.yt-genres { display: flex; flex-direction: column; gap: 10px; padding: 16px 20px; }
	.ytg-row { display: grid; grid-template-columns: 160px 1fr auto; align-items: center; gap: 12px; }
	.ytg-name { font-size: 13px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.ytg-bar-wrap { height: 8px; background: var(--glass-bg-strong); border-radius: 4px; overflow: hidden; }
	.ytg-bar { height: 100%; background: var(--youtube); border-radius: 4px; transition: width 0.4s ease; }
	.ytg-meta { font-size: 12px; color: var(--text-muted); white-space: nowrap; text-align: right; min-width: 130px; }

	/* Sección tiempo 2×2 */
	.time-surface { display: grid; grid-template-columns: 1fr 1fr; }
	.tcell { padding: 16px 18px; min-width: 0; }
	.tcell:nth-child(even) { border-left: 1px solid var(--glass-border); }
	.tcell:nth-child(n+3) { border-top: 1px solid var(--glass-border); }
	.panel-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-muted); margin-bottom: 11px; display: flex; align-items: center; gap: 8px; }
	.panel-title :global(svg) { color: var(--primary); opacity: 0.8; }

	.month-bars2 { display: flex; align-items: flex-end; gap: 8px; height: 132px; padding-bottom: 24px; position: relative; }
	.mb2-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; position: relative; }
	.mb2-bar { width: 100%; border-radius: 6px 6px 0 0; background: linear-gradient(180deg, var(--primary), oklch(0.55 0.13 300)); }
	.mb2-bar.top { background: linear-gradient(180deg, oklch(0.86 0.16 85), oklch(0.62 0.14 85)); box-shadow: 0 0 18px oklch(0.84 0.16 85 / 0.5); }
	.mb2-lbl { position: absolute; bottom: -22px; font-size: 11px; color: var(--text-muted); }
	.mb2-col.top .mb2-lbl { color: oklch(0.86 0.16 85); font-weight: 700; }
	.mb2-val { position: absolute; top: -16px; font-size: 9px; font-weight: 700; color: var(--text-dim); opacity: 0; transition: opacity .15s; }
	.mb2-col:hover .mb2-val { opacity: 1; }

	.heatwrap { overflow-x: auto; padding-bottom: 4px; }
	.heat-foot { display: flex; align-items: center; gap: 4px; margin-top: 10px; font-size: 10px; color: var(--text-muted); justify-content: flex-end; }

	.whour-blocks { display: flex; gap: 3px; margin-top: 6px; }
	.whour-block { flex: 1; aspect-ratio: 1; border-radius: 3px; }
	.whour-labels { display: flex; justify-content: space-between; margin-top: 6px; font-size: 9px; color: var(--text-dim); }
	.day-bars { display: flex; align-items: flex-end; gap: 8px; height: 100px; }
	.db-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 6px; height: 100%; }
	.db-bar { width: 100%; border-radius: 5px 5px 0 0; background: var(--primary); opacity: 0.85; min-height: 4px; }
	.db-bar.top { opacity: 1; background: linear-gradient(180deg, oklch(0.86 0.16 85), oklch(0.6 0.14 85)); box-shadow: 0 0 14px oklch(0.84 0.16 85 / 0.4); }
	.db-lbl { font-size: 10px; color: var(--text-muted); }

	/* Momento / día épico */
	.moment-surface { display: grid; grid-template-columns: 1fr 1fr; }
	.moment-surface .moment-card:nth-child(2) { border-left: 1px solid var(--glass-border); }
	.moment-card { display: flex; align-items: center; gap: 14px; padding: 15px 18px; }
	.moment-icon { width: 44px; height: 44px; border-radius: 13px; flex-shrink: 0; color: var(--primary); background: var(--glass-bg-strong); border: 1px solid var(--glass-border); display: grid; place-items: center; }
	.moment-icon.warm { color: oklch(0.72 0.18 30); }
	.moment-body { flex: 1; min-width: 0; }
	.moment-kicker { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-muted); }
	.moment-title { font-size: 15px; font-weight: 700; margin: 3px 0; }
	.moment-sub { font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.moment-stat { text-align: right; flex-shrink: 0; }
	.moment-val { font-size: 24px; font-weight: 900; color: var(--primary); line-height: 1; letter-spacing: -0.02em; }
	.moment-val.warm { color: oklch(0.72 0.18 30); }
	.moment-lbl { font-size: 10px; color: var(--text-muted); margin-top: 3px; }

	/* Canales / autores */
	.channels-dual { display: flex; gap: 16px; }
	.channels-col { flex: 1 1 0; min-width: 0; }
	.channels-col-head { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 8px; display: flex; align-items: center; gap: 7px; }
	.channels-col-head :global(svg) { color: var(--primary); opacity: 0.7; }
	.channel-grid { display: flex; flex-direction: column; }
	.channel-grid-multi { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
	.channel-card { display: flex; align-items: center; gap: 12px; height: 58px; padding: 0 16px; position: relative; transition: background .15s; }
	.channel-card:not(:first-child) { border-top: 1px solid var(--glass-border); }
	.channel-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--ch-color, var(--primary)); box-shadow: 0 0 8px var(--ch-color, var(--primary)); }
	.channel-card:hover { background: var(--glass-bg-strong); }
	.ch-rank { font-size: 11px; font-weight: 800; color: rgba(255,255,255,0.45); min-width: 20px; text-align: right; }
	.ch-avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: var(--ch-color, var(--primary)); display: grid; place-items: center; font-weight: 900; color: #fff; }
	.ch-info { flex: 1; min-width: 0; }
	.ch-name { font-size: 14px; font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.ch-meta { font-size: 11px; color: rgba(255,255,255,0.6); margin-top: 2px; }
	.ch-time { font-size: 14px; font-weight: 800; color: var(--ch-color, var(--primary)); white-space: nowrap; filter: brightness(1.3); }

	/* Pódiums */
	.podium-grid { display: grid; grid-template-columns: repeat(3, 1fr); }
	.podium-card { display: flex; align-items: center; gap: 12px; height: 68px; padding: 0 14px 0 10px; position: relative; overflow: hidden; transition: background .15s; }
	.podium-card:not(:first-child) { border-left: 1px solid var(--glass-border); }
	.podium-card:hover { background: var(--glass-bg-strong); }
	.podium-no { font-size: 30px; font-weight: 900; color: var(--accent); opacity: 0.24; line-height: 1; min-width: 26px; text-align: center; flex-shrink: 0; font-variant-numeric: tabular-nums; }
	.podium-img { flex-shrink: 0; object-fit: cover; border-radius: 8px; }
	.podium-img.land { width: 64px; height: 38px; }
	.podium-img.port { width: 31px; height: 47px; }
	.podium-img.ph { display: grid; place-items: center; background: rgba(255,255,255,0.06); color: var(--accent); }
	.podium-body { flex: 1; min-width: 0; }
	.podium-title { font-size: 13px; font-weight: 700; color: #fff; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.25; }
	.podium-sub { font-size: 10px; color: rgba(255,255,255,0.6); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.podium-badge { display: inline-block; margin-top: 4px; padding: 1px 8px; background: color-mix(in srgb, var(--accent) 20%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 42%, transparent); border-radius: 100px; font-size: 11px; font-weight: 700; color: var(--accent); filter: brightness(1.18); }

	/* Streaming */
	.streaming-grid { display: grid; }
	.plat-card { height: 114px; padding: 14px; position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 8px; }
	.plat-card:not(:first-child) { border-left: 1px solid var(--glass-border); }
	.plat-card::after { content: ''; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--pc) 20%, transparent), transparent 60%); }
	.plat-header { display: flex; align-items: center; justify-content: space-between; }
	.plat-name { font-size: 13px; font-weight: 700; color: #fff; }
	.plat-rank { font-size: 10px; font-weight: 800; color: rgba(255,255,255,0.35); }
	.plat-time { font-size: 24px; font-weight: 900; color: var(--pc); filter: brightness(1.12); font-variant-numeric: tabular-nums; line-height: 1; }
	.plat-bar-wrap { height: 5px; border-radius: 100px; background: oklch(0.30 0.01 290 / 0.7); overflow: hidden; margin-top: auto; }
	.plat-bar { height: 100%; border-radius: 100px; background: linear-gradient(90deg, var(--pc), color-mix(in srgb, var(--pc) 70%, white)); }
	.plat-footer { display: flex; align-items: baseline; justify-content: space-between; gap: 4px; }
	.plat-count { font-size: 10px; color: rgba(255,255,255,0.55); }
	.plat-avg { font-size: 10px; color: rgba(255,255,255,0.38); font-style: italic; }

	/* Reparto por tipo */
	.div-bar { display: flex; height: 12px; border-radius: 99px; overflow: hidden; gap: 1px; margin-bottom: 12px; }
	.div-seg { height: 100%; min-width: 3px; }

	/* Overview "en qué se te va el tiempo" */
	.type-overview { padding: 18px 20px; }
	.type-overview .div-bar { margin-bottom: 14px; }
	.to-legend { display: flex; flex-wrap: wrap; gap: 9px 20px; }
	.to-item { display: flex; align-items: center; gap: 7px; font-size: 12px; }
	.to-dot { width: 9px; height: 9px; border-radius: 3px; flex-shrink: 0; }
	.to-ic { color: var(--text-muted); display: inline-flex; }
	.to-nm { color: var(--text-muted); }
	.to-pct { font-weight: 800; color: var(--text); }

	/* KPI strip por tipo */
	.kpi-strip { display: grid; grid-template-columns: repeat(4, 1fr); }
	.kpi-strip .e-ic { color: var(--accent); }
	.kpi-strip .e-v { color: var(--accent); filter: brightness(1.2); }

	/* Frase de gancho por tipo */
	.tb-hook { font-size: 13px; color: var(--text-muted); margin: -2px 0 14px; line-height: 1.4; }
	.tb-hook strong { color: var(--text); font-weight: 700; }
	.type-grid { display: grid; }
	.type-card2 { padding: 14px 13px 13px; border-top: 2px solid var(--accent); display: flex; flex-direction: column; gap: 2px; }
	.type-card2:not(:first-child) { border-left: 1px solid var(--glass-border); }
	.tc2-ic { color: var(--accent); margin-bottom: 4px; }
	.tc2-nm { font-size: 13px; font-weight: 700; }
	.tc2-ct { font-size: 11px; color: var(--text-muted); }
	.tc2-tm { font-size: 18px; font-weight: 900; color: var(--accent); letter-spacing: -0.02em; filter: brightness(1.15); margin-top: 2px; }
	.tc2-pc { font-size: 10px; color: var(--text-dim); }

	/* Perfil */
	.profile-grid { display: grid; grid-template-columns: repeat(3, 1fr); margin-bottom: 20px; }
	.pcard { padding: 18px; position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 4px; }
	.pcard:not(:nth-child(3n+1)) { border-left: 1px solid var(--glass-border); }
	.pcard:nth-child(n+4) { border-top: 1px solid var(--glass-border); }
	.pcard-accent { position: absolute; top: 0; left: 0; right: 0; height: 2px; }
	.pcard-kicker { font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 5px; display: flex; align-items: center; gap: 7px; }
	.pcard-big { font-size: 34px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.05; }
	.pcard-sub { font-size: 12px; color: var(--text-muted); line-height: 1.45; margin-top: 3px; }
	.streak-flame { position: absolute; right: 12px; bottom: -14px; color: oklch(0.82 0.18 85); opacity: 0.1; pointer-events: none; }
	.streak-num { font-size: 48px; font-weight: 900; line-height: 1; letter-spacing: -0.04em; background: linear-gradient(160deg, #fff 25%, oklch(0.82 0.18 85)); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 18px oklch(0.82 0.18 85 / 0.4)); }
	.equiv-row { display: flex; align-items: baseline; gap: 10px; margin-top: 8px; }
	.equiv-times { font-size: 26px; font-weight: 900; letter-spacing: -0.03em; color: oklch(0.82 0.18 85); flex-shrink: 0; }
	.equiv-label { font-size: 12px; color: var(--text-muted); line-height: 1.35; }
	.cmp-row { display: grid; grid-template-columns: 42px 1fr 58px; align-items: center; gap: 8px; margin-top: 8px; }
	.cmp-year { font-size: 12px; font-weight: 700; color: var(--text-dim); }
	.cmp-track { height: 7px; background: rgba(255,255,255,0.07); border-radius: 99px; overflow: hidden; }
	.cmp-fill { height: 100%; border-radius: 99px; }
	.cmp-val { font-size: 12px; font-weight: 700; color: var(--text-muted); text-align: right; }
	.cmp-delta { display: inline-flex; align-items: center; gap: 5px; margin-top: 12px; font-size: 12px; font-weight: 800; padding: 4px 11px; border-radius: 99px; align-self: flex-start; }
	.cmp-delta.up { background: oklch(0.72 0.20 150 / 0.15); color: oklch(0.78 0.18 150); border: 1px solid oklch(0.72 0.20 150 / 0.3); }
	.cmp-delta.down { background: oklch(0.65 0.20 25 / 0.15); color: oklch(0.70 0.18 25); border: 1px solid oklch(0.65 0.20 25 / 0.3); }
	.rating-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
	.rating-star { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; font-weight: 800; flex-shrink: 0; }
	.rating-title { font-size: 12px; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.day-pills { display: flex; gap: 6px; margin-top: 14px; }
	.day-pill { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; font-size: 10px; font-weight: 700; background: rgba(255,255,255,0.05); color: var(--text-dim); border: 1px solid var(--glass-border); }
	.day-pill.active { background: oklch(0.68 0.18 240 / 0.25); color: oklch(0.82 0.16 240); border-color: oklch(0.68 0.18 240 / 0.5); box-shadow: 0 0 10px oklch(0.68 0.18 240 / 0.3); }
	.epic-list { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--glass-border); }
	.epic-row { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-muted); }
	.epic-row :global(svg) { flex-shrink: 0; opacity: 0.7; }
	.epic-row .t { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.epic-dur { font-weight: 700; color: var(--text-dim); flex-shrink: 0; }

	/* Logros */
	.ms-grid { display: grid; }
	.ms-card { height: 58px; padding: 12px 14px; border-left: 3px solid var(--ms-color); display: flex; align-items: center; gap: 11px; }
	.ms-card:not(:nth-child(4n+1)) { box-shadow: inset 1px 0 0 var(--glass-border); }
	.ms-card:nth-child(n+5) { border-top: 1px solid var(--glass-border); }
	.ms-ic { color: var(--ms-color); flex-shrink: 0; }
	.ms-body { min-width: 0; }
	.ms-title { font-size: 12px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.ms-sub { font-size: 10px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

	/* Share */
	.share-card { padding: 22px; border-radius: 20px; background: linear-gradient(150deg, oklch(0.17 0.045 300), oklch(0.11 0.05 300)); border: 1px solid oklch(0.42 0.06 300 / 0.5); box-shadow: 0 24px 70px rgba(0,0,0,0.6); }
	.share-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
	.share-brand { display: flex; align-items: center; gap: 11px; }
	.share-mark { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: var(--primary); background: oklch(0.20 0.05 300 / 0.8); border: 1px solid oklch(0.5 0.08 300 / 0.4); }
	.share-name { font-size: 16px; font-weight: 800; white-space: nowrap; line-height: 1.2; }
	.share-tagline { font-size: 10px; color: var(--text-muted); font-style: italic; letter-spacing: 0.04em; white-space: nowrap; }
	.share-yr { font-size: 13px; font-weight: 800; letter-spacing: 0.22em; color: var(--primary); }
	.share-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
	.share-block { padding: 13px; background: oklch(0.12 0.03 300 / 0.6); border-radius: 12px; border: 1px solid oklch(0.4 0.04 300 / 0.25); }
	.share-lbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); }
	.share-val { font-size: 15px; font-weight: 800; margin: 4px 0 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.share-val.big { font-size: 26px; color: var(--primary); }
	.share-sub { font-size: 11px; color: var(--text-muted); }
	.share-actions { display: flex; gap: 10px; flex-wrap: wrap; }
	.share-actions .btn { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
	.share-btn-primary { background: var(--primary); color: #120a1e; border: none; font-weight: 800; }

	/* Quote */
	.quote-card { display: flex; align-items: center; gap: 18px; padding: 18px 24px; margin: 20px 0; position: relative; overflow: hidden; }
	.quote-card > :global(svg) { color: var(--primary); flex-shrink: 0; opacity: 0.85; }
	.quote-text { font-size: 16px; font-weight: 600; line-height: 1.45; }
	.quote-sub { font-size: 12px; color: var(--text-muted); font-style: italic; margin-top: 4px; }

	.show-more { text-align: center; margin-top: 14px; }
	.content-grid > :global(.c-card) { align-self: start; }

	/* Game timeline */
	.gtl-surface { padding: 14px 18px 16px; }
	.gtl-header { display: grid; grid-template-columns: 164px 1fr; gap: 12px; margin-bottom: 4px; }
	.gtl-months { display: flex; justify-content: space-between; font-size: 9px; color: var(--text-dim); padding: 0 2px; }
	.gtl-rows { display: flex; flex-direction: column; }
	.gtl-row { display: grid; grid-template-columns: 164px 1fr; gap: 12px; align-items: center; padding: 6px 0; }
	.gtl-row:not(:last-child) { border-bottom: 1px solid var(--glass-border); }
	.gtl-info { display: flex; align-items: center; gap: 8px; min-width: 0; }
	.gtl-thumb { width: 28px; height: 18px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
	.gtl-thumb-ph { width: 28px; height: 18px; border-radius: 4px; background: rgba(255,255,255,0.06); display: grid; place-items: center; flex-shrink: 0; color: var(--game); }
	.gtl-title { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.gtl-track {
		position: relative; height: 28px;
		background-image: repeating-linear-gradient(90deg, var(--glass-border) 0, var(--glass-border) 1px, transparent 1px, transparent calc(100% / 12));
	}
	.gtl-baseline { position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: oklch(0.38 0.02 290 / 0.5); transform: translateY(-50%); pointer-events: none; }
	.gtl-bar { position: absolute; top: 50%; height: 4px; transform: translateY(-50%); border-radius: 2px; background: linear-gradient(90deg, oklch(0.52 0.12 300 / 0.55), var(--game)); }
	.gtl-bar.before { border-left: 3px dashed oklch(0.58 0.12 300 / 0.55); border-radius: 0 2px 2px 0; background: linear-gradient(90deg, oklch(0.45 0.10 300 / 0.35), var(--game)); }
	.gtl-dot { position: absolute; top: 50%; transform: translate(-50%, -50%); border-radius: 50%; cursor: default; }
	.gtl-dot.add { width: 8px; height: 8px; background: oklch(0.55 0.12 300); border: 1.5px solid oklch(0.72 0.14 300 / 0.9); }
	.gtl-dot.done { width: 11px; height: 11px; background: var(--game); border: 2px solid rgba(255,255,255,0.18); box-shadow: 0 0 9px color-mix(in srgb, var(--game) 75%, transparent); }
	.gtl-legend { display: flex; align-items: center; gap: 18px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--glass-border); flex-wrap: wrap; }
	.gtl-leg-item { display: flex; align-items: center; gap: 7px; font-size: 10px; color: var(--text-dim); }
	.gtl-leg-dot { display: inline-block; border-radius: 50%; flex-shrink: 0; }
	.gtl-leg-dot.add { width: 8px; height: 8px; background: oklch(0.55 0.12 300); border: 1.5px solid oklch(0.72 0.14 300 / 0.9); }
	.gtl-leg-dot.done { width: 10px; height: 10px; background: var(--game); box-shadow: 0 0 6px color-mix(in srgb, var(--game) 70%, transparent); }
	.gtl-leg-line-dash { display: inline-block; width: 18px; height: 0; border-top: 3px dashed oklch(0.58 0.12 300 / 0.65); flex-shrink: 0; }

	/* Responsive: colapsar superficies multi-columna en pantallas estrechas */
	@media (max-width: 900px) {
		.rw-hero, .time-surface, .moment-surface, .profile-grid { grid-template-columns: 1fr; }
		.rw-hero-pct, .tcell:nth-child(even), .moment-surface .moment-card:nth-child(2), .pcard:not(:nth-child(3n+1)) { border-left: none; }
		.rw-hero-pct { border-top: 1px solid var(--glass-border); }
		.tcell:nth-child(n+2), .moment-surface .moment-card:nth-child(2), .pcard:nth-child(n+2) { border-top: 1px solid var(--glass-border); }
		.estats-row { grid-template-columns: repeat(3, 1fr); }
		.estat2:nth-child(3n+1) { border-left: none; }
		.estat2:nth-child(n+4) { border-top: 1px solid var(--glass-border); }
		.channels-dual { flex-direction: column; }
		.yt-hero { flex-wrap: wrap; }
		.yt-runners { border-left: none; padding-left: 0; border-top: 1px solid var(--glass-border); padding-top: 14px; width: 100%; flex-direction: row; }
		.gtl-header { grid-template-columns: 1fr; }
		.gtl-header > div:first-child { display: none; }
		.gtl-row { grid-template-columns: 1fr; gap: 3px; }
		.gtl-track { margin-left: 0; }
	}
	@media (max-width: 560px) {
		.estats-row, .yt-stats, .kpi-strip, .share-grid { grid-template-columns: repeat(2, 1fr); }
		.podium-grid, .streaming-grid, .type-grid, .ms-grid { grid-template-columns: 1fr !important; }
		.podium-card:not(:first-child), .plat-card:not(:first-child), .type-card2:not(:first-child) { border-left: none; border-top: 1px solid var(--glass-border); }
		.ytg-row { grid-template-columns: 110px 1fr; }
		.ytg-meta { display: none; }
	}
</style>
