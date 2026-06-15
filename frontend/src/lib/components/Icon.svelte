<script lang="ts">
	/**
	 * Iconos de línea monocromos para Deus Vault.
	 * Sustituyen a los emoji del Rewind. Heredan el color con `currentColor`.
	 *
	 * Uso:  <Icon name="flame" size={18} />
	 */
	interface Props {
		name: string;
		size?: number;
		stroke?: number;
		class?: string;
	}
	let { name, size = 18, stroke = 1.8, class: klass = '' }: Props = $props();

	// Cada entrada: { f?: true (relleno), d: 'markup interno del <svg>' }
	const ICONS: Record<string, { f?: boolean; d: string }> = {
		play:       { f: true, d: '<path d="M7 4.5v15l12-7.5z"/>' },
		film:       { d: '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M7 5v14M17 5v14M2.5 12h19"/>' },
		tv:         { d: '<rect x="2.5" y="7" width="19" height="12" rx="2"/><path d="M8 3l4 4 4-4"/>' },
		music:      { d: '<circle cx="6" cy="18" r="2.6"/><circle cx="18" cy="16" r="2.6"/><path d="M8.6 18V6l11-2v12"/>' },
		book:       { d: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H19"/>' },
		game:       { d: '<rect x="2.5" y="7.5" width="19" height="10" rx="3.5"/><path d="M7 11v3M5.5 12.5h3"/><circle cx="15.8" cy="12" r=".9" fill="currentColor" stroke="none"/><circle cx="18.2" cy="14" r=".9" fill="currentColor" stroke="none"/>' },
		flame:      { f: true, d: '<path d="M12 2.5c.8 3 3.5 3.8 4.6 6.2.8 1.7.6 3.6-.5 5.1.4-1.6-.3-2.7-1.3-3.4.3 2.4-.8 3.6-2 4.6-.9.7-1.6 1.8-1.6 3a4.2 4.2 0 1 1-5.7-3.9c-.2 1 .1 1.9.8 2.5-.5-2.3.6-3.8 1.9-5C14 13.4 13 10 12 2.5z"/>' },
		trophy:     { d: '<path d="M6.5 4h11v4a5.5 5.5 0 0 1-11 0z"/><path d="M6.5 5H4v1.5a3 3 0 0 0 3 3M17.5 5H20v1.5a3 3 0 0 1-3 3M9 20h6M12 13.5V20"/>' },
		calendar:   { d: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9.5h18M8 3v4M16 3v4"/>' },
		clock:      { d: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>' },
		barChart:   { d: '<path d="M4 20h16M8 20V11M13 20V5M18 20v-6"/>' },
		star:       { f: true, d: '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.7 6.6 19.5l1.2-6-4.5-4.2 6.1-.7z"/>' },
		layers:     { d: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>' },
		share:      { d: '<path d="M4 12.5V19a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6.5"/><path d="M12 15.5V3.5M8 7l4-4 4 4"/>' },
		sparkles:   { f: true, d: '<path d="M12 2.5l1.7 5L19 9l-5.3 1.6L12 16l-1.7-5.4L5 9l5.3-1.5z"/><path d="M18.5 14l.8 2.2L21.5 17l-2.2.8-.8 2.2-.8-2.2L15.5 17l2.2-.8z"/>' },
		zap:        { f: true, d: '<path d="M13.5 2L4 13.5h6L9.5 22 20 10.5h-6z"/>' },
		activity:   { d: '<path d="M3 12h4l2.5 7 4-15 2.5 8H21"/>' },
		trendingUp: { d: '<path d="M3 16.5l6-6 4 4 7.5-7.5"/><path d="M16 7h4.5v4.5"/>' },
		list:       { d: '<path d="M8.5 6H21M8.5 12H21M8.5 18H21M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>' },
		mountain:   { d: '<path d="M3 19.5l6-11 4 6 2-3 6 8z"/>' },
		check:      { d: '<path d="M5 12.5l4.5 4.5L19 6.5"/>' },
		percent:    { d: '<path d="M5 19L19 5"/><circle cx="7" cy="7" r="2.2"/><circle cx="17" cy="17" r="2.2"/>' },
		award:      { d: '<circle cx="12" cy="9" r="5.5"/><path d="M8.5 13.5L7 21l5-2.5L17 21l-1.5-7.5"/>' },
		ban:        { d: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>' },
		chevron:    { d: '<path d="M6 9l6 6 6-6"/>' },
		refresh:    { d: '<path d="M20 11a8 8 0 1 0-2.2 5.6"/><path d="M20 4v6h-6"/>' },
	};

	const ic = $derived(ICONS[name] ?? ICONS.list);
</script>

<svg
	class={klass}
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill={ic.f ? 'currentColor' : 'none'}
	stroke={ic.f ? 'none' : 'currentColor'}
	stroke-width={stroke}
	stroke-linecap="round"
	stroke-linejoin="round"
	style="display:block; flex-shrink:0;"
	aria-hidden="true"
>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	{@html ic.d}
</svg>
