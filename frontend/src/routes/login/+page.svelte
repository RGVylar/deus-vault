<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import type { TokenResponse } from '$lib/types';

	let mode: 'login' | 'register' = $state('login');
	let email = $state('');
	let password = $state('');
	let name = $state('');
	let error = $state('');
	let loading = $state(false);

	async function submit() {
		error = '';
		loading = true;
		try {
			let res: TokenResponse;
			if (mode === 'register') {
				res = await api.post<TokenResponse>('/auth/register', { email, password, name });
			} else {
				res = await api.post<TokenResponse>('/auth/login', { email, password });
			}
			auth.login(res.access_token, res.user);
			goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : t('errors.generic');
		} finally {
			loading = false;
		}
	}
</script>

<div class="desk-login-wrap">

<!-- Desktop: brand panel (left half) -->
<div class="desk-login-brand">
	<div class="logo-title">Deus Vault</div>
	<p class="tagline">{t('login.tagline')} <em style="opacity:0.6;">memento mori.</em></p>
</div>

<!-- Form panel (right on desktop, full on mobile) -->
<div class="login-wrap">
	<div class="logo-title">DEUS VAULT</div>
	<div class="logo-tag">{t('login.tag')}</div>

	<div class="glass login-card">
		<div class="seg">
			<button class:active={mode === 'login'} onclick={() => mode = 'login'}>{t('login.signIn')}</button>
			<button class:active={mode === 'register'} onclick={() => mode = 'register'}>{t('login.createAccount')}</button>
		</div>

		<form onsubmit={e => { e.preventDefault(); submit(); }}>
			{#if mode === 'register'}
				<div class="field">
					<label for="name">{t('login.name')}</label>
					<input id="name" class="text" bind:value={name} required />
				</div>
			{/if}
			<div class="field">
				<label for="email">{t('login.email')}</label>
				<input id="email" class="text" type="email" bind:value={email} required />
			</div>
			<div class="field">
				<label for="password">{t('login.password')}</label>
				<input id="password" class="text" type="password" bind:value={password} minlength="8" required />
			</div>

			{#if error}<p class="error-msg">{error}</p>{/if}

			<button type="submit" class="btn btn-primary btn-lg" disabled={loading} style="width:100%; margin-top:8px; justify-content:center;">
				{loading ? '…' : mode === 'login' ? t('login.submitEnter') : t('login.createAccount')}
			</button>
		</form>
	</div>
</div>

</div><!-- /desk-login-wrap -->
