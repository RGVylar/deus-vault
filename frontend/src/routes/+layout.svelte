<script lang="ts">
	import '../app.css';
	import { auth } from '$lib/stores/auth.svelte';
	import { page } from '$app/state';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Bóveda', icon: '🏛️' },
		{ href: '/consumed', label: 'Consumido', icon: '✅' },
		{ href: '/random', label: 'Azar', icon: '🎲' },
		{ href: '/rewind', label: 'Rewind', icon: '📅' },
		{ href: '/settings', label: 'Ajustes', icon: '⚙️' }
	];
</script>

<div class="container page">
	{@render children()}
</div>

{#if auth.isLoggedIn}
	<nav class="bottom">
		{#each nav as item}
			<a href={item.href} class:active={page.url.pathname === item.href}>
				<span class="icon">{item.icon}</span>
				{item.label}
			</a>
		{/each}
	</nav>
{/if}
