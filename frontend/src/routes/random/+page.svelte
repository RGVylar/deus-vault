<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDuration, TYPE_ICONS, TYPE_LABELS, buildConsumeUrl } from '$lib/utils';
	import type { Content, ContentType } from '$lib/types';

	let pick: Content | null = $state(null);
	let filter: ContentType | 'all' = $state('all');
	let error = $state('');
	let spinning = $state(false);

	onMount(() => {
		if (!auth.isLoggedIn) { goto('/login'); return; }
	});

	async function roll() {
		error = '';
		spinning = true;
		try {
			const url = filter === 'all' ? '/contents/random' : `/contents/random?content_type=${filter}`;
			pick = await api.get<Content>(url);
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
</script>

{#if !auth.isLoggedIn}
	<p>Redirigiendo…</p>
{:else}
	<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:70dvh; text-align:center;">
		<h1 style="font-size:1.8rem; margin-bottom:1.5rem;">
			<span style="background:linear-gradient(135deg, var(--primary), var(--game)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
				¿Qué consumo?
			</span>
		</h1>

		<div class="tabs" style="justify-content:center; margin-bottom:1.5rem;">
			<button class:btn-secondary={filter !== 'all'} onclick={() => filter = 'all'}>Todo</button>
			<button class:btn-secondary={filter !== 'youtube'} onclick={() => filter = 'youtube'}>▶️</button>
			<button class:btn-secondary={filter !== 'movie'} onclick={() => filter = 'movie'}>🎬</button>
			<button class:btn-secondary={filter !== 'series'} onclick={() => filter = 'series'}>📺</button>
			<button class:btn-secondary={filter !== 'music'} onclick={() => filter = 'music'}>🎵</button>
			<button class:btn-secondary={filter !== 'book'} onclick={() => filter = 'book'}>📖</button>
			<button class:btn-secondary={filter !== 'game'} onclick={() => filter = 'game'}>🎮</button>
		</div>

		<button onclick={roll} disabled={spinning}
			style="font-size:1.1rem; padding:1rem 2.5rem; border-radius:99px; margin-bottom:2rem;">
			{spinning ? '🎲 Girando…' : '🎲 Elegir al azar'}
		</button>

		{#if error}
			<p class="error">{error}</p>
		{/if}

		{#if pick}
			{@const link = buildConsumeUrl(pick)}
			<div class="content-card random-pick" style="max-width:400px; width:100%;">
				{#if pick.thumbnail}
					<img class="thumb" src={pick.thumbnail} alt="" style="width:80px; height:80px;" />
				{:else}
					<div class="thumb" style="display:flex; align-items:center; justify-content:center; font-size:2rem; width:80px; height:80px;">
						{TYPE_ICONS[pick.content_type] || '📄'}
					</div>
				{/if}
				<div class="info">
					<div class="title" style="font-size:1rem;">{pick.title}</div>
					<div class="meta">
						<span class="badge {pick.content_type}">{TYPE_LABELS[pick.content_type]}</span>
						{#if pick.duration_minutes > 0}
							<span>⏱ {formatDuration(pick.duration_minutes)}</span>
						{/if}
						{#if pick.author}
							<span>{pick.author}</span>
						{/if}
					</div>
					<div class="actions" style="margin-top:0.6rem;">
						{#if link}
							<a href={link} target="_blank" rel="noopener">
								<button>🚀 Consumir</button>
							</a>
						{/if}
						<button onclick={() => consume(pick!.id)} style="background:rgba(79,255,170,0.15); color:var(--game); box-shadow:none;">✓ Hecho</button>
						<button class="btn-secondary" onclick={roll}>🔄 Otro</button>
					</div>
				</div>
			</div>
		{/if}
	</div>
{/if}
