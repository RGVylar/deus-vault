<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { linksApi } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import type { VaultInvitePeek, VaultPartner } from '$lib/types';

	// La invitación viaja en la URL (WhatsApp, Telegram…). Esta pantalla es la
	// única que la canjea: mira quién invita, pide sesión si no la hay y, al
	// aceptar, enlaza las dos bóvedas y quema el token.
	const token = $derived(page.params.token ?? '');

	let phase = $state<'loading' | 'invalid' | 'ready' | 'accepting' | 'done'>('loading');
	let invite = $state<VaultInvitePeek | null>(null);
	let partner = $state<VaultPartner | null>(null);
	let error = $state('');

	const isOwn = $derived(!!invite && !!auth.user && invite.inviter_id === auth.user.id);
	const loginHref = $derived(`/login?next=${encodeURIComponent(`/link/${token}`)}`);

	onMount(async () => {
		try {
			invite = await linksApi.peekInvite(token);
			phase = 'ready';
		} catch {
			phase = 'invalid';
		}
	});

	async function accept() {
		phase = 'accepting';
		error = '';
		try {
			partner = await linksApi.acceptInvite(token);
			phase = 'done';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : t('errors.generic');
			phase = 'ready';
		}
	}
</script>

<div class="link-wrap">
	<div class="glass link-card">
		<div class="link-mark">🔗</div>
		<h1 class="link-title">{t('link.title')}</h1>

		{#if phase === 'loading'}
			<p class="muted">{t('link.loading')}</p>

		{:else if phase === 'invalid'}
			<p class="link-bad">{t('link.invalid')}</p>
			<a href="/" class="btn" style="justify-content:center;">Deus Vault</a>

		{:else if phase === 'done' && partner}
			<p class="link-prompt">{@html t('link.done', { name: partner.name })}</p>
			<a href="/random" class="btn btn-primary" style="justify-content:center;">{t('link.goRandom')}</a>

		{:else if invite}
			<p class="link-prompt">{@html t('link.prompt', { name: invite.inviter_name })}</p>
			<p class="muted link-explain">{t('link.explain')}</p>

			{#if !auth.isLoggedIn}
				<p class="muted">{t('link.needLogin')}</p>
				<a href={loginHref} class="btn btn-primary" style="justify-content:center;">{t('link.loginButton')}</a>
			{:else if isOwn}
				<p class="link-bad">{t('link.own')}</p>
				<a href="/settings" class="btn" style="justify-content:center;">{t('nav.settings')}</a>
			{:else}
				{#if error}<p class="link-bad">{error}</p>{/if}
				<button class="btn btn-primary btn-lg" onclick={accept} disabled={phase === 'accepting'} style="justify-content:center;">
					{phase === 'accepting' ? t('link.accepting') : t('link.accept')}
				</button>
				<a href="/" class="btn" style="justify-content:center;">{t('link.decline')}</a>
			{/if}
		{/if}
	</div>
</div>

<style>
	.link-wrap { display: flex; justify-content: center; padding: 24px 0; }
	.link-card {
		width: 100%; max-width: 420px; padding: 28px 24px; border-radius: var(--radius);
		display: flex; flex-direction: column; gap: 14px; text-align: center;
	}
	.link-mark { font-size: 40px; line-height: 1; }
	.link-title { font-size: 22px; font-weight: 800; margin: 0; }
	.link-prompt { font-size: 15px; line-height: 1.5; margin: 0; }
	.link-prompt :global(strong) { color: var(--primary); }
	.link-explain { font-size: 13px; line-height: 1.5; margin: 0; }
	.link-bad {
		margin: 0; padding: 10px 14px; border-radius: var(--radius-sm); font-size: 13px;
		background: color-mix(in oklab, var(--danger) 12%, var(--glass-bg-weak));
		border: 1px solid color-mix(in oklab, var(--danger) 30%, transparent);
	}
	.link-card :global(.btn) { width: 100%; }
</style>
