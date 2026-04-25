<script lang="ts">
	import '../app.css';
	import { auth } from '$lib/stores/auth.svelte';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let { children } = $props();

	const navMain = [
		{ href: '/',         label: 'Bóveda',   icon: '🏛️' },
		{ href: '/consumed', label: 'Consumido', icon: '✓'  },
		{ href: '/random',   label: 'Azar',      icon: '🎲' },
		{ href: '/rewind',   label: 'Rewind',    icon: '📊' },
	];

	const navBottom = [
		{ href: '/',         label: 'Bóveda',   icon: '🏛️' },
		{ href: '/consumed', label: 'Consumido', icon: '✅' },
		{ href: '/random',   label: 'Azar',      icon: '🎲' },
		{ href: '/rewind',   label: 'Rewind',    icon: '📅' },
		{ href: '/settings', label: 'Ajustes',   icon: '⚙️' },
	];

	function applyPrefs() {
		try {
			const theme     = localStorage.getItem('deus_vault_theme')     ?? 'dark';
			const wallpaper = localStorage.getItem('deus_vault_wallpaper') ?? 'aurora';
			const blur      = localStorage.getItem('deus_vault_blur')      ?? '28';
			const el = document.documentElement;
			el.setAttribute('data-theme',     theme === 'light' ? 'light' : '');
			el.setAttribute('data-wallpaper', wallpaper === 'aurora' ? '' : wallpaper);
			el.style.setProperty('--blur', `${blur}px`);
		} catch (e) {}
	}

	function logout() {
		auth.logout();
		goto('/login');
	}

	onMount(() => {
		applyPrefs();
		window.addEventListener('deus_vault_appearance_changed', applyPrefs);
		return () => window.removeEventListener('deus_vault_appearance_changed', applyPrefs);
	});
</script>

<!-- Animated mesh wallpaper (fixed, z:0) -->
<div class="wallpaper">
	<div class="blob b1"></div>
	<div class="blob b2"></div>
	<div class="blob b3"></div>
	<div class="blob b4"></div>
	<div class="grain"></div>
</div>

<!-- App shell: transparent on mobile, sidebar+main grid on desktop -->
<div class="app-shell">

	<!-- Sidebar (desktop only — hidden via CSS on mobile) -->
	{#if auth.isLoggedIn}
	<aside class="sidebar">
		<div class="sb-brand">
			<div class="sb-brand-mark">⛧</div>
			<div>
				<div class="sb-brand-name">Deus Vault</div>
				<div class="sb-brand-sub">memento mori</div>
			</div>
		</div>

		<div class="sb-section">Tu bóveda</div>
		{#each navMain as item}
			<a href={item.href} class="sb-item" class:active={page.url.pathname === item.href}>
				<span class="sbi-ico">{item.icon}</span>
				<span>{item.label}</span>
			</a>
		{/each}

		<div class="sb-section">Cuenta</div>
		<a href="/settings" class="sb-item" class:active={page.url.pathname === '/settings'}>
			<span class="sbi-ico">⚙️</span><span>Ajustes</span>
		</a>
		<button class="sb-item" onclick={logout}>
			<span class="sbi-ico">↪</span><span>Cerrar sesión</span>
		</button>

		<div class="sb-spacer"></div>
		<div class="sb-user">
			<div class="av">{auth.user?.name?.charAt(0).toUpperCase() ?? '?'}</div>
			<div class="sb-user-info">
				<div class="nm">{auth.user?.name ?? ''}</div>
				<div class="em">{auth.user?.email ?? ''}</div>
			</div>
		</div>
	</aside>
	{/if}

	<!-- Page content -->
	<div class="page-scroll">
		{@render children()}
	</div>
</div>

<!-- Mobile tab bar (hidden on desktop via CSS) -->
{#if auth.isLoggedIn}
	<nav class="tab-bar">
		{#each navBottom as item}
			<a href={item.href} class="tab-item" class:active={page.url.pathname === item.href}>
				<span class="ti-ico">{item.icon}</span>
				{item.label}
			</a>
		{/each}
	</nav>
{/if}
