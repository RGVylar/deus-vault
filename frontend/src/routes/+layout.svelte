<script lang="ts">
	import '../app.css';
	import { auth } from '$lib/stores/auth.svelte';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Bóveda', icon: '🏛️' },
		{ href: '/consumed', label: 'Consumido', icon: '✅' },
		{ href: '/random', label: 'Azar', icon: '🎲' },
		{ href: '/rewind', label: 'Rewind', icon: '📅' },
		{ href: '/settings', label: 'Ajustes', icon: '⚙️' },
	];

	// Apply persisted appearance prefs on mount + when changed from settings
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

	onMount(() => {
		applyPrefs();
		window.addEventListener('deus_vault_appearance_changed', applyPrefs);
		return () => window.removeEventListener('deus_vault_appearance_changed', applyPrefs);
	});
</script>

<!-- Animated mesh wallpaper -->
<div class="wallpaper">
	<div class="blob b1"></div>
	<div class="blob b2"></div>
	<div class="blob b3"></div>
	<div class="blob b4"></div>
	<div class="grain"></div>
</div>

<!-- Page content -->
<div class="page-scroll">
	{@render children()}
</div>

<!-- Glass pill tab bar -->
{#if auth.isLoggedIn}
	<nav class="tab-bar">
		{#each nav as item}
			<a href={item.href} class="tab-item" class:active={page.url.pathname === item.href}>
				<span class="ti-ico">{item.icon}</span>
				{item.label}
			</a>
		{/each}
	</nav>
{/if}
