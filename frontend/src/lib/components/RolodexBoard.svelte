<script lang="ts">
	import type { Content, ContentType } from '$lib/types';
	import RolodexColumn from './RolodexColumn.svelte';

	let {
		groups,
		onSelect
	}: { groups: { type: ContentType; items: Content[] }[]; onSelect: (c: Content) => void } = $props();
</script>

{#if groups.length > 0}
	<div class="rolodex-board">
		{#each groups as group (group.type)}
			<RolodexColumn type={group.type} items={group.items} {onSelect} />
		{/each}
	</div>
{/if}

<style>
	.rolodex-board {
		display: flex;
		gap: 4px;
		overflow-x: auto;
		padding: 4px 2px 8px;
		scrollbar-width: thin;
	}

	@media (max-width: 720px) {
		.rolodex-board {
			flex-direction: column;
			gap: 0;
			overflow-x: visible;
		}
	}
</style>
