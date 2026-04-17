<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, ContentType, VaultStats } from '$lib/types';
	import { effectiveDuration } from '$lib/types';

	let contents: Content[] = $state([]);
	let stats: VaultStats | null = $state(null);
	let filter: ContentType | 'all' = $state('all');
	let loading = $state(true);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
		load();
	});

	async function load() {
		loading = true;
		try {
			[stats, contents] = await Promise.all([
				api.get<VaultStats>('/contents/stats'),
				api.get<Content[]>('/contents?consumed=true')
			]);
		} finally { loading = false; }
	}

	$effect(() => {
		if (!auth.isLoggedIn) return;
		const type = filter;
		const url = type === 'all' ? '/contents?consumed=true' : `/contents?consumed=true&content_type=${type}`;
		api.get<Content[]>(url).then(r => contents = r);
	});

	async function unconsume(id: number) {
		await api.post(`/contents/${id}/unconsume`);
		load();
	}
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}
	<h1>Consumido</h1>

	{#if stats}
		<div class="hero-number" style="padding:0.5rem 0;">
			<div class="number" style="font-size:2rem;">{formatDuration(stats.total_consumed_minutes)}</div>
			<div class="unit">de contenido consumido</div>
		</div>
		<div class="stat-row">
			<div class="stat-pill">
				<span>✅</span> <span class="val">{stats.consumed_count}</span> items
			</div>
		</div>
	{/if}

	<div class="tabs">
		<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todos</button>
		<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
		<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬</button>
		<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖</button>
		<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮</button>
	</div>

	{#if loading}
		<p style="text-align:center; color:var(--text-muted);">Cargando…</p>
	{:else if contents.length === 0}
		<div class="card" style="text-align:center; padding:2rem;">
			<p style="color:var(--text-muted);">Aún no has consumido nada. ¡A ello!</p>
		</div>
	{:else}
		<div style="display:flex; flex-direction:column; gap:0.5rem;">
			{#each contents as c (c.id)}
				{@const link = buildConsumeUrl(c)}
				<div class="content-card" style="opacity:0.75;">
					{#if c.thumbnail}
						<img class="thumb" src={c.thumbnail} alt="" />
					{:else}
						<div class="thumb" style="display:flex; align-items:center; justify-content:center; font-size:1.5rem;">
							{TYPE_ICONS[c.content_type] || '📄'}
						</div>
					{/if}
					<div class="info">
						<div class="title">{c.title}</div>
						<div class="meta">
							<span class="badge {c.content_type}">{TYPE_LABELS[c.content_type]}</span>
							{#if c.content_type === 'series'}
								{#if c.seasons && c.seasons > 0}
									<span>📺 {c.seasons}T</span>
								{/if}
								{#if c.episode_count && c.episode_count > 0}
									<span>{c.episode_count} ep</span>
								{/if}
								{#if c.duration_minutes > 0}
									<span>⏱ {formatDuration(c.duration_minutes)}/ep</span>
								{/if}
								{#if c.episode_count && c.episode_count > 0 && c.duration_minutes > 0}
									<span class="series-total">~{formatDuration(c.duration_minutes * c.episode_count)} total</span>
								{/if}
							{:else if c.duration_minutes > 0}
								<span>⏱ {formatDuration(c.duration_minutes)}</span>
							{/if}
							{#if c.consumed_at}
								<span>📅 {new Date(c.consumed_at).toLocaleDateString('es')}</span>
							{/if}
						</div>
						<div class="actions">
							{#if link}
								<a href={link} target="_blank" rel="noopener">
									<button class="btn-secondary">Abrir</button>
								</a>
							{/if}
							<button class="btn-secondary" onclick={() => unconsume(c.id)}>↩ Devolver</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}
