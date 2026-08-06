<script lang="ts">
	import type { Content } from '$lib/types';
	import { TYPE_COLOR } from '$lib/utils';

	let {
		items,
		targetId,
		spinToken,
		onRoll,
		onSettled
	}: {
		items: Content[];
		targetId: number | null;
		spinToken: number;
		onRoll: () => void;
		onSettled?: () => void;
	} = $props();

	// Misma geometría de pila que RolodexColumn, a escala grande — esto es la
	// pieza central de la página, no una miniatura de navegación.
	const FULL_H = 230;
	const SLIVER_H = 16;
	const GAP = 5;
	const STACK0 = FULL_H / 2 + SLIVER_H / 2 + GAP;
	const MAX_A = 6;

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

	let cardEls: (HTMLDivElement | null)[] = [];
	let position = 0;
	let spinning = $state(false);
	let animId: number | null = null;
	let lastToken = 0;

	function render() {
		const n = items.length;
		cardEls.forEach((card, i) => {
			if (!card || i >= n) return;
			let raw = i - position;
			if (n > 0) raw -= n * Math.round(raw / n);
			const { a, h, y, opacity } = metrics(raw);
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
			card.classList.toggle('is-front', a < 0.05);
			const label = card.querySelector('.t') as HTMLElement | null;
			if (label) label.style.opacity = a < 0.4 ? String(Math.max(0, 1 - a / 0.4)) : '0';
			const tint = card.querySelector('.tint') as HTMLElement | null;
			if (tint) tint.style.opacity = Math.min(0.9, a * 0.55).toFixed(2);
		});
	}

	function spinTo(targetIndex: number) {
		const n = items.length;
		if (n === 0) return;
		if (animId != null) cancelAnimationFrame(animId);
		spinning = true;
		const laps = 3 + Math.floor(Math.random() * 2);
		const startPos = position;
		const forward = (((targetIndex - startPos) % n) + n) % n;
		const totalDistance = laps * n + forward;
		const duration = 1900;
		const t0 = performance.now();

		function frame(now: number) {
			const t = Math.min(1, (now - t0) / duration);
			const eased = 1 - Math.pow(1 - t, 3);
			position = ((startPos + totalDistance * eased) % n + n) % n;
			render();
			if (t < 1) {
				animId = requestAnimationFrame(frame);
			} else {
				position = targetIndex;
				render();
				spinning = false;
				animId = null;
				onSettled?.();
			}
		}
		animId = requestAnimationFrame(frame);
	}

	$effect(() => {
		if (spinToken !== lastToken && spinToken > 0) {
			lastToken = spinToken;
			const idx = items.findIndex((c) => c.id === targetId);
			if (idx >= 0) spinTo(idx);
		}
	});

	$effect(() => {
		render();
	});
</script>

<div
	class="roller-stage"
	class:spinning
	onclick={() => !spinning && onRoll()}
	role="button"
	tabindex="0"
	onkeydown={(e) => {
		if ((e.key === 'Enter' || e.key === ' ') && !spinning) {
			onRoll();
			e.preventDefault();
		}
	}}
>
	<div class="roller-drum">
		{#each items as c, i (c.id + '-' + i)}
			<div
				class="roller-card"
				bind:this={cardEls[i]}
				style="--col-accent: {TYPE_COLOR[c.content_type] ?? 'var(--primary)'}"
			>
				{#if c.thumbnail}
					<img
						src={c.thumbnail}
						alt=""
						class="art"
						onerror={(e) => {
							(e.currentTarget as HTMLElement).style.display = 'none';
						}}
					/>
				{:else}
					<div class="art ph"></div>
				{/if}
				<div class="tint"></div>
				<div class="veil"></div>
				<div class="t">{c.title}</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.roller-stage {
		position: relative;
		width: 100%;
		max-width: 460px;
		height: 320px;
		margin: 0 auto;
		overflow: hidden;
		-webkit-mask-image: linear-gradient(180deg, transparent, black 6%, black 94%, transparent);
		mask-image: linear-gradient(180deg, transparent, black 6%, black 94%, transparent);
		cursor: pointer;
		border-radius: var(--radius);
	}
	.roller-stage:focus-visible {
		outline: 2px solid var(--primary);
		outline-offset: 6px;
	}
	.roller-stage.spinning {
		cursor: default;
	}

	.roller-drum {
		position: absolute;
		inset: 0;
	}

	.roller-card {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 100%;
		border-radius: var(--radius-sm);
		overflow: hidden;
		background: var(--glass-bg);
		border: 1px solid var(--glass-border);
		box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
		will-change: transform, height, opacity;
	}
	.roller-card.is-front {
		box-shadow:
			0 16px 40px rgba(0, 0, 0, 0.6),
			0 0 0 1px color-mix(in oklab, var(--col-accent) 55%, transparent),
			0 0 32px -8px var(--col-accent);
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
	.tint {
		position: absolute;
		inset: 0;
		background: var(--col-accent);
		opacity: 0;
		mix-blend-mode: hard-light;
	}
	.veil {
		position: absolute;
		inset: 0;
		background: linear-gradient(180deg, transparent 35%, rgba(0, 0, 0, 0.88) 100%);
	}
	.t {
		position: absolute;
		left: 20px;
		right: 20px;
		bottom: 16px;
		font-size: 22px;
		font-weight: 800;
		color: #fff;
		letter-spacing: -0.015em;
		line-height: 1.25;
		text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		transition: opacity 0.2s;
	}

	@media (max-width: 640px) {
		.roller-stage {
			height: 240px;
		}
		.t {
			font-size: 17px;
			left: 14px;
			right: 14px;
			bottom: 12px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.roller-card {
			transition: none !important;
		}
	}
</style>
