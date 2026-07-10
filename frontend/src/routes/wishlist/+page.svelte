<script lang="ts">
	import { onMount } from 'svelte';
	import { wishlistApi } from '$lib/api';
	import { t, tc, fmtCurrency } from '$lib/i18n/index.svelte';
	import type { WishlistItem, WishlistStats, ProductLookupResult } from '$lib/types';

	// ── State ──────────────────────────────────────────────────────────────
	let items = $state<WishlistItem[]>([]);
	let stats = $state<WishlistStats | null>(null);
	let tab = $state<'pending' | 'purchased' | 'gifted' | 'all'>('pending');
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Salary (localStorage only)
	let hourlyRate = $state(0);

	// Add modal
	let showModal = $state(false);
	let modalUrl = $state('');
	let modalLooking = $state(false);
	let modalLookupResult = $state<ProductLookupResult | null>(null);
	let modalLookupError = $state<string | null>(null);
	let modalTitle = $state('');
	let modalPrice = $state('');
	let modalStore = $state('');
	let modalNotes = $state('');
	let saving = $state(false);

	// Edit modal
	let editItem = $state<WishlistItem | null>(null);
	let editTitle = $state('');
	let editPrice = $state('');
	let editStore = $state('');
	let editNotes = $state('');
	let editSaving = $state(false);

	// ── Computed ───────────────────────────────────────────────────────────
	let displayed = $derived(
		tab === 'pending'   ? items.filter(i => !i.purchased && !i.gifted) :
		tab === 'purchased' ? items.filter(i => i.purchased && !i.gifted)  :
		tab === 'gifted'    ? items.filter(i => i.gifted)                  : items
	);

	function hoursForPrice(price: number | null): string {
		if (!price || !hourlyRate) return '';
		const hours = price / hourlyRate;
		if (hours < 1) return `${Math.round(hours * 60)}min`;
		const h = Math.floor(hours);
		const m = Math.round((hours - h) * 60);
		return m > 0 ? `${h}h ${m}min` : `${h}h`;
	}

	function fmtPrice(p: number | null): string {
		if (p == null) return '—';
		return fmtCurrency(p, 'EUR');
	}

	function storeColor(store: string | null): string {
		const s = (store ?? '').toLowerCase();
		if (s.includes('amazon'))  return 'var(--youtube)';
		if (s.includes('apple'))   return 'oklch(0.77 0.14 240)';
		if (s.includes('steam'))   return 'oklch(0.84 0.17 150)';
		return 'var(--primary)';
	}

	// ── Load ───────────────────────────────────────────────────────────────
	async function load() {
		loading = true;
		error = null;
		try {
			[items, stats] = await Promise.all([wishlistApi.list(), wishlistApi.stats()]);
		} catch (e: any) {
			error = e.message ?? t('wishlist.loadError');
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		const saved = localStorage.getItem('deus_vault_hourly_rate');
		if (saved) hourlyRate = parseFloat(saved) || 0;
		load();
	});

	// ── Lookup ─────────────────────────────────────────────────────────────
	async function lookupUrl() {
		if (!modalUrl.trim()) return;
		modalLooking = true;
		modalLookupResult = null;
		modalLookupError = null;
		try {
			const r = await wishlistApi.lookup(modalUrl.trim());
			modalLookupResult = r;
			if (r.title)  modalTitle = r.title;
			if (r.price)  modalPrice = String(r.price);
			if (r.store)  modalStore = r.store;
		} catch (e: any) {
			modalLookupError = t('wishlist.lookupError');
		} finally {
			modalLooking = false;
		}
	}

	function openModal() {
		modalUrl = '';
		modalTitle = '';
		modalPrice = '';
		modalStore = '';
		modalNotes = '';
		modalLookupResult = null;
		modalLookupError = null;
		saving = false;
		showModal = true;
	}

	function closeModal() {
		showModal = false;
	}

	async function saveItem() {
		if (!modalTitle.trim()) return;
		saving = true;
		try {
			const price = modalPrice ? parseFloat(modalPrice.replace(',', '.')) : null;
			await wishlistApi.create({
				title: modalTitle.trim(),
				url: modalUrl.trim() || null,
				price: isNaN(price ?? NaN) ? null : price,
				image_url: modalLookupResult?.image_url ?? null,
				store: modalStore.trim() || null,
				notes: modalNotes.trim() || null,
				source_id: modalLookupResult?.source_id ?? null,
			});
			await load();
			closeModal();
		} catch (e: any) {
			error = e.message;
		} finally {
			saving = false;
		}
	}

	// ── Edit ───────────────────────────────────────────────────────────────
	function openEdit(item: WishlistItem) {
		editItem = item;
		editTitle = item.title;
		editPrice = item.price != null ? String(item.price) : '';
		editStore = item.store ?? '';
		editNotes = item.notes ?? '';
		editSaving = false;
	}

	function closeEdit() { editItem = null; }

	async function saveEdit() {
		if (!editItem) return;
		editSaving = true;
		try {
			const price = editPrice ? parseFloat(editPrice.replace(',', '.')) : null;
			await wishlistApi.update(editItem.id, {
				title: editTitle.trim(),
				price: isNaN(price ?? NaN) ? null : price,
				store: editStore.trim() || null,
				notes: editNotes.trim() || null,
			});
			await load();
			closeEdit();
		} catch (e: any) {
			error = e.message;
		} finally {
			editSaving = false;
		}
	}

	// ── Actions ────────────────────────────────────────────────────────────
	async function togglePurchase(item: WishlistItem) {
		try {
			if (item.purchased) await wishlistApi.unpurchase(item.id);
			else                await wishlistApi.purchase(item.id);
			await load();
		} catch (e: any) { error = e.message; }
	}

	async function toggleGift(item: WishlistItem) {
		try {
			if (item.gifted) await wishlistApi.ungift(item.id);
			else             await wishlistApi.gift(item.id);
			await load();
		} catch (e: any) { error = e.message; }
	}

	async function deleteItem(item: WishlistItem) {
		if (!confirm(t('wishlist.confirmDelete', { title: item.title }))) return;
		try {
			await wishlistApi.delete(item.id);
			await load();
		} catch (e: any) { error = e.message; }
	}
</script>

<!-- ── Page ──────────────────────────────────────────────────────────────── -->
<div class="page">

	<div class="page-header">
		<div class="page-header-top">
			<div>
				<h1 class="page-title">{t('wishlist.title')}</h1>
				{#if stats}
					<p class="page-sub">{tc('wishlist.summary', stats.total_items, { price: fmtPrice(stats.total_cost) })}</p>
				{/if}
			</div>
			<button class="btn btn-primary" onclick={openModal}>{t('wishlist.add')}</button>
		</div>

		<!-- Stats -->
		{#if stats}
		<div class="stats-row">
			<div class="stat-card">
				<div class="stat-label">{t('wishlist.pending')}</div>
				<div class="stat-value">{fmtPrice(stats.pending_cost)}</div>
				<div class="stat-sub">{tc('wishlist.itemsSuffix', stats.pending_items)}</div>
			</div>
			<div class="stat-card accent-amber">
				<div class="stat-label">{t('wishlist.toWork')}</div>
				<div class="stat-value">
					{#if hourlyRate && stats.pending_cost}
						{hoursForPrice(stats.pending_cost)}
					{:else}
						—
					{/if}
				</div>
				<div class="stat-sub">
					{#if hourlyRate}
						{t('wishlist.atRate', { rate: fmtPrice(hourlyRate) })}
					{:else}
						<a href="/settings#salary" class="stat-link">{t('wishlist.configureSalary')}</a>
					{/if}
				</div>
			</div>
			<div class="stat-card accent-green">
				<div class="stat-label">{t('wishlist.spent')}</div>
				<div class="stat-value">{fmtPrice(stats.purchased_cost)}</div>
				<div class="stat-sub">{t('wishlist.purchasedSuffix', { count: stats.purchased_items })}</div>
			</div>
		</div>
		{/if}

		<!-- Tabs -->
		<div class="tabs">
			<button class="tab" class:active={tab === 'pending'}   onclick={() => tab = 'pending'}>{t('wishlist.tabs.pending')}</button>
			<button class="tab" class:active={tab === 'purchased'} onclick={() => tab = 'purchased'}>{t('wishlist.tabs.purchased')}</button>
			<button class="tab" class:active={tab === 'gifted'}    onclick={() => tab = 'gifted'}>{t('wishlist.tabs.gifted')}</button>
			<button class="tab" class:active={tab === 'all'}       onclick={() => tab = 'all'}>{t('wishlist.tabs.all')}</button>
		</div>
	</div>

	<!-- Error -->
	{#if error}
		<div class="error-banner">{error} <button onclick={() => error = null}>×</button></div>
	{/if}

	<!-- List -->
	{#if loading}
		<div class="empty-state">{t('wishlist.loading')}</div>
	{:else if displayed.length === 0}
		<div class="empty-state">
			{tab === 'pending'   ? t('wishlist.emptyPending') :
			 tab === 'purchased' ? t('wishlist.emptyPurchased') :
			 tab === 'gifted'    ? t('wishlist.emptyGifted') :
			 t('wishlist.emptyAll')}
			{#if tab !== 'purchased'}
				<br><button class="btn btn-primary" style="margin-top:12px" onclick={openModal}>{t('wishlist.addFirst')}</button>
			{/if}
		</div>
	{:else}
		<div class="items-list">
			{#each displayed as item (item.id)}
				<div class="item-card" class:purchased={item.purchased || item.gifted}>
					<div class="item-accent" style="background:{storeColor(item.store)}"></div>

					{#if item.image_url}
						<img class="item-thumb" src={item.image_url} alt={item.title} loading="lazy" />
					{:else}
						<div class="item-thumb item-thumb-placeholder">{item.store === 'Steam' ? '🎮' : '🛍️'}</div>
					{/if}

					<div class="item-body">
						{#if item.url}
						<a class="item-name" class:strikethrough={item.purchased || item.gifted} href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>
					{:else}
						<div class="item-name" class:strikethrough={item.purchased || item.gifted}>{item.title}</div>
					{/if}
						{#if item.store}
							<div class="item-store">
								<span class="store-dot" style="background:{storeColor(item.store)}"></span>
								{item.store}
							</div>
						{/if}
						{#if item.price && hourlyRate && !item.purchased}
							<div class="item-work">{t('wishlist.workTime', { time: hoursForPrice(item.price) })}</div>
						{/if}
						{#if item.notes}
							<div class="item-notes">{item.notes}</div>
						{/if}
					</div>

					<div class="item-right">
						<div class="item-price" class:muted={item.purchased || item.gifted}>{fmtPrice(item.price)}</div>
						<div class="item-actions">
							{#if item.gifted}
								<span class="badge-gifted">{t('wishlist.gifted')}</span>
								<button class="icon-btn" title={t('wishlist.undoGift')} onclick={() => toggleGift(item)}>↩</button>
							{:else if item.purchased}
								{#if item.source_id && item.store === 'Steam'}
									<span class="badge-vault">{t('wishlist.inVault')}</span>
								{:else}
									<span class="badge-bought">{t('wishlist.bought')}</span>
								{/if}
								<button class="icon-btn" title={t('wishlist.undoPurchase')} onclick={() => togglePurchase(item)}>↩</button>
							{:else}
								<button class="icon-btn icon-btn-edit" title={t('wishlist.edit')} onclick={() => openEdit(item)}>✎</button>
								<button class="icon-btn icon-btn-buy"  title={t('wishlist.markPurchased')} onclick={() => togglePurchase(item)}>✓</button>
								<button class="icon-btn icon-btn-gift" title={t('wishlist.giftedToMe')}  onclick={() => toggleGift(item)}>🎁</button>
							{/if}
							<button class="icon-btn icon-btn-del" title={t('wishlist.delete')} onclick={() => deleteItem(item)}>✕</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<!-- ── Add modal ─────────────────────────────────────────────────────────── -->
{#if showModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
		<div class="modal">
			<div class="modal-header">
				<span class="modal-title">{t('wishlist.addItem')}</span>
				<button class="modal-close" onclick={closeModal}>×</button>
			</div>

			<div class="field">
				<label class="field-label">{t('wishlist.productUrl')}</label>
				<div class="url-row">
					<input
						class="text"
						type="url"
						placeholder="https://amazon.es/..."
						bind:value={modalUrl}
						onkeydown={(e) => e.key === 'Enter' && lookupUrl()}
					/>
					<button class="btn btn-primary" onclick={lookupUrl} disabled={modalLooking || !modalUrl.trim()}>
						{modalLooking ? '…' : '🔍'}
					</button>
				</div>
			</div>

			{#if modalLookupError}
				<p class="lookup-error">{modalLookupError}</p>
			{/if}

			{#if modalLookupResult?.image_url}
				<div class="preview-row">
					<img class="preview-img" src={modalLookupResult.image_url} alt="preview" />
					<div class="preview-info">
						<div class="preview-name">{modalLookupResult.title ?? ''}</div>
						{#if modalLookupResult.price}
							<div class="preview-price">{fmtPrice(modalLookupResult.price)}</div>
						{/if}
					</div>
				</div>
			{/if}

			<div class="field">
				<label class="field-label">{t('wishlist.name')}</label>
				<input class="text" type="text" placeholder={t('wishlist.namePlaceholder')} bind:value={modalTitle} />
			</div>

			<div class="fields-row">
				<div class="field">
					<label class="field-label">{t('wishlist.price')}</label>
					<input class="text" type="text" placeholder="0,00" bind:value={modalPrice} />
				</div>
				<div class="field">
					<label class="field-label">{t('wishlist.store')}</label>
					<input class="text" type="text" placeholder={t('wishlist.storePlaceholder')} bind:value={modalStore} />
				</div>
			</div>

			<div class="field">
				<label class="field-label">{t('wishlist.notes')}</label>
				<textarea class="text" rows="2" placeholder={t('wishlist.notesPlaceholder')} bind:value={modalNotes}></textarea>
			</div>

			{#if modalLookupResult?.content_type_hint === 'game'}
				<div class="steam-hint">{t('wishlist.steamHint')}</div>
			{/if}

			{#if modalTitle.trim() && modalPrice && hourlyRate}
				<div class="hours-hint">
					{t('wishlist.hoursHint', { hours: hoursForPrice(parseFloat(modalPrice.replace(',', '.'))), rate: fmtPrice(hourlyRate) })}
				</div>
			{/if}

			<div class="modal-actions">
				<button class="btn" onclick={closeModal}>{t('wishlist.cancel')}</button>
				<button class="btn btn-primary" onclick={saveItem} disabled={saving || !modalTitle.trim()}>
					{saving ? t('wishlist.saving') : t('wishlist.save')}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Edit modal ─────────────────────────────────────────────────────────── -->
{#if editItem}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={(e) => { if (e.target === e.currentTarget) closeEdit(); }}>
		<div class="modal">
			<div class="modal-header">
				<span class="modal-title">{t('wishlist.editItem')}</span>
				<button class="modal-close" onclick={closeEdit}>×</button>
			</div>

			<div class="field">
				<label class="field-label">{t('wishlist.name')}</label>
				<input class="text" type="text" bind:value={editTitle} />
			</div>

			<div class="fields-row">
				<div class="field">
					<label class="field-label">{t('wishlist.price')}</label>
					<input class="text" type="text" bind:value={editPrice} />
				</div>
				<div class="field">
					<label class="field-label">{t('wishlist.store')}</label>
					<input class="text" type="text" bind:value={editStore} />
				</div>
			</div>

			<div class="field">
				<label class="field-label">{t('wishlist.notes')}</label>
				<textarea class="text" rows="2" bind:value={editNotes}></textarea>
			</div>

			<div class="modal-actions">
				<button class="btn" onclick={closeEdit}>{t('wishlist.cancel')}</button>
				<button class="btn btn-primary" onclick={saveEdit} disabled={editSaving || !editTitle.trim()}>
					{editSaving ? t('wishlist.saving') : t('wishlist.save')}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
.page {
	display: flex;
	flex-direction: column;
	gap: 0;
	padding-bottom: 120px;
}

.page-header {
	position: sticky;
	top: 0;
	z-index: 10;
	background: var(--glass-bg-strong);
	backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
	-webkit-backdrop-filter: blur(var(--blur)) saturate(var(--saturate));
	border-bottom: 1px solid var(--glass-border);
	padding: 20px 20px 0;
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.page-header-top {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
}

.page-title {
	font-size: 26px;
	font-weight: 800;
	color: var(--text);
	line-height: 1.1;
}

.page-sub {
	font-size: 13px;
	color: var(--text-muted);
	margin-top: 2px;
}

/* Stats */
.stats-row {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 10px;
}

.stat-card {
	background: var(--glass-bg);
	backdrop-filter: blur(16px);
	border: 1px solid var(--glass-border);
	border-radius: var(--radius-xs);
	padding: 12px 14px;
}

.stat-label {
	font-size: 11px;
	color: var(--text-dim);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	margin-bottom: 4px;
}

.stat-value {
	font-size: 20px;
	font-weight: 700;
	color: var(--text);
	line-height: 1;
}

.accent-amber .stat-value { color: oklch(0.82 0.18 75); }
.accent-green  .stat-value { color: oklch(0.77 0.17 150); }

.stat-sub {
	font-size: 11px;
	color: var(--text-dim);
	margin-top: 4px;
}

.stat-link {
	color: var(--primary);
	text-decoration: none;
	font-size: 11px;
}

/* Tabs */
.tabs {
	display: flex;
	gap: 0;
}

.tab {
	background: none;
	border: none;
	border-bottom: 2px solid transparent;
	padding: 10px 16px;
	font-size: 13px;
	color: var(--text-muted);
	cursor: pointer;
	transition: color 0.15s, border-color 0.15s;
}

.tab.active {
	color: var(--primary);
	border-bottom-color: var(--primary);
	font-weight: 600;
}

/* Items */
.items-list {
	display: flex;
	flex-direction: column;
	gap: 1px;
	padding: 16px 16px 0;
}

.item-card {
	background: var(--glass-bg);
	backdrop-filter: blur(16px) saturate(1.4);
	border: 1px solid var(--glass-border);
	border-radius: var(--radius-sm);
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 12px 14px;
	position: relative;
	overflow: hidden;
	transition: border-color 0.15s, transform 0.15s;
	margin-bottom: 8px;
}

.item-card:hover {
	border-color: var(--glass-border-bright);
	transform: translateY(-1px);
}

.item-card.purchased {
	opacity: 0.6;
}

.item-accent {
	position: absolute;
	left: 0;
	top: 0;
	bottom: 0;
	width: 3px;
}

.item-thumb {
	width: 52px;
	height: 52px;
	border-radius: 8px;
	object-fit: cover;
	flex-shrink: 0;
	background: var(--glass-bg-weak);
}

.item-thumb-placeholder {
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 22px;
	border: 1px solid var(--glass-border);
}

.item-body {
	flex: 1;
	min-width: 0;
}

.item-name {
	font-size: 14px;
	font-weight: 600;
	color: var(--text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	text-decoration: none;
}

a.item-name:hover {
	color: var(--primary);
	text-decoration: underline;
}

.strikethrough { text-decoration: line-through; }

.item-store {
	display: flex;
	align-items: center;
	gap: 5px;
	font-size: 12px;
	color: var(--text-muted);
	margin-top: 3px;
}

.store-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
}

.item-work {
	font-size: 12px;
	color: var(--text-dim);
	margin-top: 4px;
}

.item-notes {
	font-size: 12px;
	color: var(--text-dim);
	margin-top: 3px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.item-right {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 8px;
	flex-shrink: 0;
}

.item-price {
	font-size: 15px;
	font-weight: 700;
	color: var(--text);
}

.item-price.muted {
	text-decoration: line-through;
	color: var(--text-dim);
}

.item-actions {
	display: flex;
	align-items: center;
	gap: 5px;
}

.icon-btn {
	width: 28px;
	height: 28px;
	border-radius: 7px;
	border: 1px solid var(--glass-border);
	background: var(--glass-bg-weak);
	color: var(--text-muted);
	font-size: 13px;
	cursor: pointer;
	display: flex;
	align-items: center;
	justify-content: center;
	transition: background 0.15s, color 0.15s;
}

.icon-btn:hover { background: var(--glass-bg-strong); color: var(--text); }
.icon-btn-buy  { color: oklch(0.77 0.17 150); border-color: oklch(0.77 0.17 150 / 0.4); }
.icon-btn-del  { color: var(--danger); border-color: oklch(0.72 0.22 20 / 0.3); }
.icon-btn-edit { color: var(--primary); }

.badge-bought {
	font-size: 11px;
	color: oklch(0.77 0.17 150);
	background: oklch(0.77 0.17 150 / 0.15);
	border: 1px solid oklch(0.77 0.17 150 / 0.3);
	border-radius: 999px;
	padding: 2px 8px;
}

.badge-gifted {
	font-size: 11px;
	color: oklch(0.82 0.18 330);
	background: oklch(0.82 0.18 330 / 0.15);
	border: 1px solid oklch(0.82 0.18 330 / 0.3);
	border-radius: 999px;
	padding: 2px 8px;
}

.badge-vault {
	font-size: 11px;
	color: oklch(0.84 0.17 150);
	background: oklch(0.84 0.17 150 / 0.15);
	border: 1px solid oklch(0.84 0.17 150 / 0.3);
	border-radius: 999px;
	padding: 2px 8px;
}

.icon-btn-gift { color: oklch(0.82 0.18 330); border-color: oklch(0.82 0.18 330 / 0.4); }

/* Empty / error */
.empty-state {
	text-align: center;
	padding: 60px 20px;
	color: var(--text-muted);
	font-size: 14px;
	line-height: 1.6;
}

.error-banner {
	margin: 12px 16px 0;
	background: oklch(0.72 0.22 20 / 0.15);
	border: 1px solid oklch(0.72 0.22 20 / 0.35);
	border-radius: var(--radius-xs);
	color: var(--danger);
	font-size: 13px;
	padding: 8px 12px;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.error-banner button {
	background: none;
	border: none;
	color: inherit;
	cursor: pointer;
	font-size: 16px;
}

/* Modal */
.overlay {
	position: fixed;
	inset: 0;
	background: rgba(0,0,0,0.5);
	backdrop-filter: blur(8px);
	z-index: 100;
	display: flex;
	align-items: flex-end;
	justify-content: center;
	padding: 16px;
}

@media (min-width: 600px) {
	.overlay { align-items: center; }
}

.modal {
	background: var(--glass-bg-strong);
	backdrop-filter: blur(40px) saturate(2);
	border: 1px solid var(--glass-border-bright);
	border-radius: 28px;
	padding: 24px;
	width: 100%;
	max-width: 520px;
	display: flex;
	flex-direction: column;
	gap: 14px;
	box-shadow: 0 -10px 60px rgba(0,0,0,0.5);
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.modal-title {
	font-size: 16px;
	font-weight: 700;
	color: var(--text);
}

.modal-close {
	background: none;
	border: none;
	color: var(--text-muted);
	font-size: 22px;
	cursor: pointer;
	line-height: 1;
}

.field { display: flex; flex-direction: column; gap: 5px; }
.field-label { font-size: 12px; color: var(--text-muted); }

.fields-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 10px;
}

.url-row { display: flex; gap: 8px; }
.url-row .text { flex: 1; }
.url-row .btn { flex-shrink: 0; padding: 0 16px; }

.preview-row {
	display: flex;
	align-items: center;
	gap: 12px;
	background: var(--glass-bg-weak);
	border: 1px solid var(--glass-border);
	border-radius: var(--radius-xs);
	padding: 10px 12px;
}

.preview-img {
	width: 48px;
	height: 48px;
	border-radius: 6px;
	object-fit: cover;
	flex-shrink: 0;
}

.preview-info { flex: 1; min-width: 0; }

.preview-name {
	font-size: 13px;
	font-weight: 600;
	color: var(--text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.preview-price {
	font-size: 13px;
	color: var(--primary);
	margin-top: 2px;
}

.lookup-error {
	font-size: 12px;
	color: var(--danger);
}

.steam-hint {
	font-size: 12px;
	color: oklch(0.84 0.17 150);
	background: oklch(0.84 0.17 150 / 0.1);
	border: 1px solid oklch(0.84 0.17 150 / 0.25);
	border-radius: var(--radius-xs);
	padding: 8px 12px;
}

.hours-hint {
	font-size: 12px;
	color: var(--primary);
	background: oklch(0.78 0.15 300 / 0.1);
	border: 1px solid oklch(0.78 0.15 300 / 0.2);
	border-radius: var(--radius-xs);
	padding: 8px 12px;
}

.modal-actions {
	display: flex;
	gap: 10px;
	justify-content: flex-end;
}

/* Responsive */
@media (min-width: 980px) {
	.items-list { padding: 20px 28px 0; }
	.page-header { padding: 24px 28px 0; }
	.stats-row { gap: 12px; }
	.stat-value { font-size: 22px; }
}
</style>
