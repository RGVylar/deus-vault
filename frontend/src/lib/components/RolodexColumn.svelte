<script lang="ts">
	import type { Content, ContentType } from '$lib/types';
	import { TYPE_ICONS, TYPE_COLOR, typeLabel } from '$lib/utils';

	let { type, items, onSelect }: { type: ContentType; items: Content[]; onSelect: (c: Content) => void } = $props();

	// Geometría de la pila apilada — fija, no depende de cuántos items tenga la
	// columna. Dejar que el radio de un tambor 3D creciera con N fue el bug de
	// la primera versión (la carta frontal se deformaba con columnas grandes).
	const FULL_H = 72;   // alto de la carta activa
	const SLIVER_H = 8;  // alto de una carta apilada (solo el canto)
	const GAP = 3;
	const STACK0 = FULL_H / 2 + SLIVER_H / 2 + GAP;
	const MAX_A = 7;     // más allá de esto, ni se renderiza

	function metrics(offset: number) {
		const a = Math.abs(offset);
		let h: number, y: number;
		if (a <= 1) {
			h = FULL_H + (SLIVER_H - FULL_H) * a;
			y = Math.sign(offset) * STACK0 * a;
		} else {
			h = SLIVER_H;
			y = Math.sign(offset) * (STACK0 + (a - 1) * (SLIVER_H + GAP));
		}
		const opacity = a > MAX_A ? 0 : a <= 1 ? 1 : Math.max(0.2, 1 - (a - 1) * 0.13);
		return { a, h, y, opacity };
	}

	let stageEl: HTMLDivElement | undefined;
	// Array de refs puramente imperativo (para mutar estilos fuera del ciclo
	// reactivo en cada tick de rueda/arrastre) — Svelte avisa de que
	// `bind:this` en un índice de array no-reactivo dentro de un {#each} no
	// se puede rastrear con precisión, pero funciona correctamente igualmente.
	let cardEls: (HTMLDivElement | null)[] = [];
	let position = 0;
	let dragging = false;
	let startY = 0;
	let startPos = 0;
	let settleTimer: ReturnType<typeof setTimeout> | undefined;

	const N = items.length;
	const clamp = (p: number) => Math.max(0, Math.min(N - 1, p));

	function render() {
		cardEls.forEach((card, i) => {
			if (!card) return;
			const { a, h, y, opacity } = metrics(i - position);
			if (opacity <= 0) {
				card.style.display = 'none';
				card.classList.remove('is-front');
				return;
			}
			card.style.display = '';
			card.style.height = h.toFixed(1) + 'px';
			card.style.transform = `translate(-50%, -50%) translateY(${y.toFixed(1)}px)`;
			card.style.opacity = opacity.toFixed(3);
			card.style.zIndex = String(1000 - Math.round(a * 10));
			card.style.pointerEvents = a < 0.5 ? 'auto' : 'none';
			card.classList.toggle('is-front', a < 0.05);
			const label = card.querySelector('.t') as HTMLElement | null;
			if (label) label.style.opacity = a < 0.4 ? String(Math.max(0, 1 - a / 0.4)) : '0';
		});
	}

	function withTransition(fn: () => void) {
		cardEls.forEach(
			(c) =>
				c &&
				(c.style.transition =
					'transform .4s cubic-bezier(.22,1,.36,1), height .4s cubic-bezier(.22,1,.36,1), opacity .3s')
		);
		fn();
		clearTimeout(settleTimer);
		settleTimer = setTimeout(() => cardEls.forEach((c) => c && (c.style.transition = '')), 420);
	}
	function settle() {
		withTransition(() => {
			position = Math.round(clamp(position));
			render();
		});
	}
	function liveUpdate(next: number) {
		cardEls.forEach((c) => c && (c.style.transition = ''));
		position = clamp(next);
		render();
		clearTimeout(settleTimer);
		settleTimer = setTimeout(settle, 200);
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		liveUpdate(position + e.deltaY * 0.0035);
	}
	function onPointerDown(e: PointerEvent) {
		dragging = true;
		startY = e.clientY;
		startPos = position;
		try {
			stageEl?.setPointerCapture(e.pointerId);
		} catch (_) {}
		cardEls.forEach((c) => c && (c.style.transition = ''));
	}
	function onPointerMove(e: PointerEvent) {
		if (!dragging) return;
		position = clamp(startPos - (e.clientY - startY) / 58);
		render();
	}
	function endDrag() {
		if (!dragging) return;
		dragging = false;
		settle();
	}
	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
			position = clamp(Math.round(position) - 1);
			settle();
			e.preventDefault();
		} else if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
			position = clamp(Math.round(position) + 1);
			settle();
			e.preventDefault();
		} else if (e.key === 'Enter' || e.key === ' ') {
			onSelect(items[Math.round(position)]);
			e.preventDefault();
		}
	}

	$effect(() => {
		render();
	});
</script>

<div class="rolodex-col" style="--col-accent: {TYPE_COLOR[type] ?? 'var(--primary)'}">
	<div class="rolodex-col-head">
		<div class="icn">{TYPE_ICONS[type] ?? '📄'}</div>
		<div class="lbl">{typeLabel(type)}</div>
		<div class="cnt">{items.length}</div>
	</div>

	<div
		class="rolodex-stage"
		bind:this={stageEl}
		tabindex="0"
		role="listbox"
		aria-label={typeLabel(type)}
		onwheel={onWheel}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={endDrag}
		onpointercancel={endDrag}
		onkeydown={onKeydown}
	>
		<div class="rolodex-drum">
			{#each items as c, i (c.id)}
				<div class="rolodex-card" bind:this={cardEls[i]} onclick={() => onSelect(c)} role="presentation">
					{#if c.thumbnail}
						<img
							src={c.thumbnail}
							alt=""
							class="art"
							onerror={(e) => {
								const img = e.currentTarget as HTMLElement;
								img.style.display = 'none';
							}}
						/>
					{:else}
						<div class="art ph"></div>
					{/if}
					<div class="veil"></div>
					<div class="t">{c.title}</div>
				</div>
			{/each}
		</div>
	</div>

	<div class="rolodex-hint">↕</div>
</div>

<style>
	.rolodex-col {
		flex: 1 1 0;
		min-width: 150px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 4px 6px 10px;
		border-radius: var(--radius-sm);
		transition: background 0.25s;
	}
	.rolodex-col:hover {
		background: color-mix(in oklab, var(--col-accent) 6%, transparent);
	}

	.rolodex-col-head {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 3px;
	}
	.icn {
		width: 30px;
		height: 30px;
		border-radius: var(--radius-xs);
		display: grid;
		place-items: center;
		font-size: 15px;
		background: color-mix(in oklab, var(--col-accent) 22%, var(--glass-bg-strong));
		border: 1px solid color-mix(in oklab, var(--col-accent) 45%, transparent);
	}
	.lbl {
		font-size: 11.5px;
		font-weight: 700;
		color: var(--text);
		letter-spacing: -0.01em;
	}
	.cnt {
		font-size: 10px;
		color: var(--text-dim);
		font-variant-numeric: tabular-nums;
	}

	.rolodex-stage {
		position: relative;
		width: 148px;
		height: 220px;
		overflow: hidden;
		-webkit-mask-image: linear-gradient(180deg, transparent, black 10%, black 90%, transparent);
		mask-image: linear-gradient(180deg, transparent, black 10%, black 90%, transparent);
		cursor: grab;
		touch-action: pan-y;
		border-radius: var(--radius-sm);
	}
	.rolodex-stage:active {
		cursor: grabbing;
	}
	.rolodex-stage:focus-visible {
		outline: 2px solid var(--col-accent);
		outline-offset: 4px;
	}

	.rolodex-drum {
		position: absolute;
		inset: 0;
	}

	.rolodex-card {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 138px;
		border-radius: var(--radius-xs);
		overflow: hidden;
		background: var(--glass-bg);
		border: 1px solid var(--glass-border);
		box-shadow: 0 6px 16px rgba(0, 0, 0, 0.45);
		cursor: pointer;
		will-change: transform, height, opacity;
	}
	.rolodex-card.is-front {
		box-shadow:
			0 10px 26px rgba(0, 0, 0, 0.55),
			0 0 0 1px color-mix(in oklab, var(--col-accent) 55%, transparent);
	}
	.art {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.art.ph {
		background: color-mix(in oklab, var(--col-accent) 16%, var(--glass-bg-weak));
	}
	.veil {
		position: absolute;
		inset: 0;
		background: linear-gradient(180deg, transparent 30%, rgba(0, 0, 0, 0.88) 100%);
	}
	.t {
		position: absolute;
		left: 8px;
		right: 8px;
		bottom: 6px;
		font-size: 11px;
		font-weight: 700;
		color: #fff;
		letter-spacing: -0.01em;
		line-height: 1.25;
		text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		transition: opacity 0.2s;
	}

	.rolodex-hint {
		font-size: 10px;
		color: var(--text-dim);
		opacity: 0.7;
	}

	@media (max-width: 720px) {
		.rolodex-col {
			flex-direction: row;
			align-items: center;
			justify-content: flex-start;
			gap: 16px;
			padding: 10px 12px;
		}
		.rolodex-col-head {
			flex-direction: row;
			gap: 8px;
			min-width: 108px;
		}
		.rolodex-stage {
			width: 148px;
			height: 150px;
			margin-left: auto;
		}
		.rolodex-hint {
			display: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.rolodex-card {
			transition: none !important;
		}
	}
</style>
