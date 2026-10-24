<script lang="ts">
	/**
	 * Icono Lucide del tipo de contenido. Hereda tamaño (1em, en app.css) y color
	 * del texto, así que ocupa lo mismo que el emoji de antes.
	 */
	import { FileText } from '@lucide/svelte';
	import { TYPE_ICONS } from '$lib/utils';

	let { type, class: klass = '' }: { type: string; class?: string } = $props();
	const Cmp = $derived(TYPE_ICONS[type] ?? FileText);
</script>

<Cmp class={klass} />
