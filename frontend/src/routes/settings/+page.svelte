<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';

	onMount(() => {
		if (!auth.isLoggedIn) goto('/login');
	});

	function logout() {
		auth.logout();
		goto('/login');
	}
</script>

{#if auth.isLoggedIn}
	<h1>Ajustes</h1>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.3rem;">Sesión</p>
		<p style="font-weight:600;">{auth.user?.name}</p>
		<p style="font-size:0.85rem; color:var(--text-muted);">{auth.user?.email}</p>
	</div>

	<button class="btn-danger" onclick={logout} style="width:100%;">Cerrar sesión</button>
{/if}
