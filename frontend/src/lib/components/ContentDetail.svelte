<script lang="ts">
	import { t, fmtDate as fmtDateI18n } from '$lib/i18n/index.svelte';
	import {
		TYPE_ICONS, TYPE_COLOR, PROVIDER_LABELS,
		formatDuration, typeLabel, buildConsumeUrl,
		resolveProvider, shortProviderName, providerNameToKey
	} from '$lib/utils';
	import type { Content } from '$lib/types';

	interface Props {
		content: Content;
		onClose: () => void;
		onEdit: (c: Content) => void;
		onConsume: (id: number) => void;
		onAbandon: (id: number) => void;
		onDelete: (id: number) => void;
		onRefresh: (c: Content) => void;
		onTogglePin: (c: Content) => void;
		canRefresh: (c: Content) => boolean;
		refreshingId: number | null;
	}
	let { content, onClose, onEdit, onConsume, onAbandon, onDelete, onRefresh, onTogglePin, canRefresh, refreshingId }: Props = $props();

	let confirmingDelete = $state(false);

	const accent = $derived(TYPE_COLOR[content.content_type] ?? 'var(--primary)');
	const icon = $derived(TYPE_ICONS[content.content_type] ?? '📄');
	const consumeUrl = $derived(buildConsumeUrl(content));

	const genresList = $derived(
		(content.genres ?? '').split(',').map(g => g.trim()).filter(Boolean)
	);

	const providerList = $derived.by(() => {
		if (content.streaming_providers) {
			try {
				const raw = JSON.parse(content.streaming_providers) as string[];
				return raw.map(name => ({
					paid: name.startsWith('$'),
					name: name.startsWith('$') ? name.slice(1) : name,
				}));
			} catch { /* fall through */ }
		}
		const prov = resolveProvider(content);
		return prov ? [{ paid: false, name: PROVIDER_LABELS[prov] ?? prov }] : [];
	});
</script>

<div class="overlay" onclick={onClose} role="presentation">
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="modal glass-strong detail-sheet" onclick={e => e.stopPropagation()} role="dialog" tabindex="-1" style="--card-accent:{accent};">
		<div class="modal-handle"></div>

		<div class="d-hero" class:has-thumb={!!content.thumbnail} style={content.thumbnail ? `background-image:url('${content.thumbnail}')` : ''}>
			{#if !content.thumbnail}<div class="d-hero-icon">{icon}</div>{/if}
			<button class="d-close" onclick={onClose} aria-label={t('common.close')}>✕</button>
			<div class="d-hero-title">{content.title}</div>
		</div>

		<div class="d-row">
			<span class="badge">{typeLabel(content.content_type)}</span>
			{#if content.rating}<span class="d-rating">★ {content.rating.toFixed(1)}</span>{/if}
			{#each providerList.slice(0, 4) as p}
				<span class="provider-badge provider-{providerNameToKey(p.name)}" class:provider-paid={p.paid}>
					{shortProviderName(p.name)}{p.paid ? ' €' : ''}
				</span>
			{/each}
		</div>

		{#if genresList.length}
			<div class="d-row d-genres">
				{#each genresList as g}<span class="d-chip">{g}</span>{/each}
			</div>
		{/if}

		{#if content.synopsis}
			<div class="d-section">
				<div class="d-label">{t('home.detail.synopsis')}</div>
				<p class="d-synopsis">{content.synopsis}</p>
			</div>
		{/if}

		<div class="d-section">
			<div class="d-label">{t('home.detail.info')}</div>
			<div class="d-meta-grid">
				<div class="d-meta-item">
					<div class="d-meta-k">{t('home.detail.inVaultSince')}</div>
					<div class="d-meta-v">{fmtDateI18n(new Date(content.created_at), { day: 'numeric', month: 'short', year: 'numeric' })}</div>
				</div>
				{#if content.started_at}
					<div class="d-meta-item">
						<div class="d-meta-k">{t('home.startDate')}</div>
						<div class="d-meta-v">{fmtDateI18n(new Date(content.started_at), { day: 'numeric', month: 'short', year: 'numeric' })}</div>
					</div>
				{/if}
				{#if content.author}
					<div class="d-meta-item">
						<div class="d-meta-k">{t('home.authorLabel')}</div>
						<div class="d-meta-v">{content.author}</div>
					</div>
				{/if}
				{#if content.content_type === 'book' && content.page_count}
					<div class="d-meta-item">
						<div class="d-meta-k">{t('home.pagesLabel')}</div>
						<div class="d-meta-v">{content.page_count}</div>
					</div>
				{/if}
				{#if content.duration_minutes > 0}
					<div class="d-meta-item">
						<div class="d-meta-k">{t('home.detail.duration')}</div>
						<div class="d-meta-v">{formatDuration(content.duration_minutes)}{content.content_type === 'series' ? '/ep' : ''}</div>
					</div>
				{/if}
				{#if content.times_consumed && content.times_consumed > 1}
					<div class="d-meta-item">
						<div class="d-meta-k">{t('consumed.timesConsumed', { count: content.times_consumed })}</div>
						<div class="d-meta-v">↻</div>
					</div>
				{/if}
			</div>
		</div>

		{#if content.notes}
			<div class="d-section">
				<div class="d-label">{t('home.detail.notes')}</div>
				<p class="d-notes">{content.notes}</p>
			</div>
		{/if}

		{#if content.trailer_url}
			<div class="d-section">
				<div class="d-label">{t('home.detail.trailerSection')}</div>
				<a class="d-trailer" href={content.trailer_url} target="_blank" rel="noopener">
					<span class="d-play">▶</span> {t('home.trailerBtn')}
				</a>
			</div>
		{/if}

		<div class="d-actions">
			<button class="btn btn-primary" onclick={() => onConsume(content.id)}>✓ {t('home.markConsumed')}</button>
			{#if consumeUrl}
				<a href={consumeUrl} target="_blank" rel="noopener"><button class="btn">{t('consumed.open')}</button></a>
			{/if}
			<span class="d-cold-actions">
				<button class="btn" class:pin-active={content.pinned} onclick={() => onTogglePin(content)} title={content.pinned ? t('home.removePriority') : t('home.markPriority')} style="opacity:{content.pinned ? 1 : 0.5};">{content.pinned ? '📌' : '📍'}</button>
				<button class="btn" onclick={() => onEdit(content)} title={t('common.edit')}>✏️</button>
				{#if canRefresh(content)}
					<button class="btn" onclick={() => onRefresh(content)} disabled={refreshingId !== null} title={t('home.updateMetadata')} style={refreshingId === content.id ? 'animation: spin 0.8s linear infinite; opacity:0.7;' : ''}>↻</button>
				{/if}
				<button class="btn btn-abandon" onclick={() => onAbandon(content.id)} title={t('home.abandonBtn')}>🚫</button>
				{#if confirmingDelete}
					<button class="btn btn-danger" onclick={() => onDelete(content.id)}>{t('common.yes')}</button>
					<button class="btn" onclick={() => confirmingDelete = false}>{t('common.no')}</button>
				{:else}
					<button class="btn btn-danger" onclick={() => confirmingDelete = true}>✕</button>
				{/if}
			</span>
		</div>
	</div>
</div>

<style>
	.detail-sheet { padding: 0 0 20px; overflow: hidden; }
	.detail-sheet .modal-handle { margin-top: 12px; }

	.d-hero {
		position: relative;
		height: 180px;
		margin-top: 14px;
		background-size: cover;
		background-position: center;
		background-color: color-mix(in oklab, var(--card-accent) 20%, var(--glass-bg-weak));
	}
	.d-hero.has-thumb::after {
		content: '';
		position: absolute; inset: 0;
		background: linear-gradient(180deg, transparent 40%, oklch(0.15 0.02 290 / .92) 100%);
	}
	.d-hero-icon { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 48px; opacity: .4; }
	.d-close {
		position: absolute; top: 12px; right: 12px; z-index: 2; width: 28px; height: 28px; border-radius: 50%;
		background: rgba(0,0,0,.35); border: 1px solid var(--glass-border); color: var(--text);
		display: flex; align-items: center; justify-content: center; font-size: 13px; cursor: pointer;
	}
	.d-hero-title {
		position: absolute; left: 20px; right: 20px; bottom: 14px; z-index: 1;
		font-size: 19px; font-weight: 800; letter-spacing: -0.01em; color: #fff;
		text-shadow: 0 2px 10px rgba(0,0,0,.7);
	}

	.d-row { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin: 14px 20px 0; }
	.d-genres { gap: 6px; }
	.d-chip {
		font-size: 10px; font-weight: 600; padding: 3px 9px; border-radius: 999px;
		border: 1px solid var(--glass-border-bright); color: var(--text-muted);
	}
	.d-rating { color: oklch(0.85 0.15 85); font-size: 12px; font-weight: 700; }
	.provider-badge {
		font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 999px;
		background: rgba(255,255,255,0.08); border: 1px solid var(--glass-border); color: var(--text-muted);
	}

	.d-section { margin: 18px 20px 0; }
	.d-label {
		font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
		color: var(--text-dim); margin-bottom: 6px;
	}
	.d-synopsis, .d-notes { font-size: 13px; line-height: 1.6; color: var(--text-muted); margin: 0; }
	.d-notes { font-style: italic; border-left: 2px solid var(--glass-border-bright); padding-left: 10px; }

	.d-meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 18px; }
	.d-meta-item { font-size: 12px; }
	.d-meta-k { color: var(--text-dim); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 2px; }
	.d-meta-v { color: var(--text); font-weight: 600; }

	.d-trailer {
		display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: var(--radius-xs);
		background: var(--glass-bg-weak); border: 1px solid var(--glass-border); font-size: 12px; color: var(--text);
		text-decoration: none; width: fit-content;
	}
	.d-play {
		width: 24px; height: 24px; border-radius: 50%; background: var(--card-accent, var(--primary)); color: #1a1204;
		display: flex; align-items: center; justify-content: center; font-size: 10px; flex-shrink: 0;
	}

	.d-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 22px 20px 0; }
	.btn-primary { background: color-mix(in oklab, var(--card-accent) 30%, var(--glass-bg)); border-color: color-mix(in oklab, var(--card-accent) 50%, transparent); font-weight: 700; }
	.d-cold-actions { display: flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }
</style>
