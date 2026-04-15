<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';

	let readingWpm = 200;
	let readingWordsPerPage = 300;

	onMount(() => {
		if (!auth.isLoggedIn) goto('/login');
		try {
			const stored = localStorage.getItem('deus_vault_reading_wpm');
			if (stored) readingWpm = Number(stored) || readingWpm;
			const storedPages = localStorage.getItem('deus_vault_words_per_page');
			if (storedPages) readingWordsPerPage = Number(storedPages) || readingWordsPerPage;
		} catch (e) {}
	});

	function logout() {
		auth.logout();
		goto('/login');
	}

	function dispatchSettingsChanged() {
		try {
			const ev = new CustomEvent('deus_vault_settings_changed', { detail: { readingWpm, readingWordsPerPage } });
			window.dispatchEvent(ev);
		} catch (e) {}
	}

	function saveLocalSettings() {
		try { localStorage.setItem('deus_vault_reading_wpm', String(readingWpm)); localStorage.setItem('deus_vault_words_per_page', String(readingWordsPerPage)); } catch(e){}
		dispatchSettingsChanged();
	}

	function resetLocalSettings() {
		readingWpm = 200; readingWordsPerPage = 300;
		try { localStorage.removeItem('deus_vault_reading_wpm'); localStorage.removeItem('deus_vault_words_per_page'); } catch(e){}
		dispatchSettingsChanged();
	}
</script>

{#if auth.isLoggedIn}
	<h1>Ajustes</h1>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.3rem;">Sesión</p>
		<p style="font-weight:600;">{auth.user?.name}</p>
		<p style="font-size:0.85rem; color:var(--text-muted);">{auth.user?.email}</p>
	</div>

	<div class="card" style="margin-bottom:1rem;">
		<p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:0.3rem;">Lectura</p>
		<label for="settings-wpm" style="display:block; font-weight:600; margin-bottom:0.25rem;">Velocidad de lectura (palabras/min)</label>
		<input id="settings-wpm" type="number" bind:value={readingWpm} min="50" max="2000" />
		<label for="settings-pages" style="display:block; font-weight:600; margin:0.5rem 0 0.25rem;">Palabras por página (promedio)</label>
		<input id="settings-pages" type="number" bind:value={readingWordsPerPage} min="50" max="1000" />
		<p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.5rem;">Estos ajustes se guardan localmente en tu navegador y se usan para estimar la duración de libros.</p>
		<div style="display:flex; gap:0.5rem; margin-top:1rem;">
			<button class="" onclick={saveLocalSettings} style="flex:1;">Guardar ajustes</button>
			<button class="btn-secondary" onclick={resetLocalSettings} style="flex:1;">Restablecer</button>
		</div>
	</div>

	<button class="btn-danger" onclick={logout} style="width:100%">Cerrar sesión</button>
{/if}
