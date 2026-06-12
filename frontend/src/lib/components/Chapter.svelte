<script lang="ts">
	/**
	 * Capítulo plegable del Rewind. Renderiza el divider como cabecera clicable
	 * y colapsa/expande su contenido (transición grid 1fr↔0fr). Persiste el estado
	 * en localStorage por `id`.
	 *
	 * Uso:
	 *   <Chapter id="youtube" label="YOUTUBE" icon="play">
	 *     …contenido…
	 *   </Chapter>
	 */
	import { onMount, type Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	interface Props {
		id: string;
		label: string;
		icon?: string;
		children: Snippet;
	}
	let { id, label, icon = '', children }: Props = $props();

	let collapsed = $state(false);

	onMount(() => {
		try { collapsed = localStorage.getItem('rw-collapse-' + id) === '1'; } catch { /* ignore */ }
	});

	function toggle() {
		collapsed = !collapsed;
		try { localStorage.setItem('rw-collapse-' + id, collapsed ? '1' : '0'); } catch { /* ignore */ }
	}
</script>

<div class="collapse-group" class:collapsed>
	<div
		class="deep-divider collapse-head"
		role="button"
		tabindex="0"
		aria-expanded={!collapsed}
		onclick={toggle}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
	>
		<div class="dd-line"></div>
		<span class="dd-label">{#if icon}<Icon name={icon} size={12} />{/if} {label}</span>
		<div class="dd-line"></div>
		<span class="collapse-chevron"><Icon name="chevron" size={16} /></span>
	</div>
	<div class="collapse-body"><div class="collapse-inner">{@render children()}</div></div>
</div>

<style>
	.collapse-group { display: block; }
	.deep-divider { display: flex; align-items: center; gap: 16px; margin: 30px 0 20px; }
	.dd-line { flex: 1; height: 1px; background: linear-gradient(90deg, transparent, var(--glass-border), transparent); }
	.dd-label { font-size: 10px; font-weight: 900; letter-spacing: 0.26em; color: var(--text-dim); display: flex; align-items: center; gap: 8px; white-space: nowrap; }
	.dd-label :global(svg) { color: var(--primary); opacity: 0.7; }
	.collapse-head { cursor: pointer; user-select: none; }
	.collapse-head:hover .dd-label { color: var(--text); }
	.collapse-chevron { display: inline-flex; color: var(--text-dim); transition: transform .3s ease; }
	.collapse-group.collapsed .collapse-chevron { transform: rotate(-90deg); }
	.collapse-body { display: grid; grid-template-rows: 1fr; transition: grid-template-rows .32s cubic-bezier(.3,.8,.4,1); }
	.collapse-group.collapsed .collapse-body { grid-template-rows: 0fr; }
	.collapse-inner { overflow: hidden; min-height: 0; }
	.collapse-group.collapsed .deep-divider { margin-bottom: 30px; }
</style>
