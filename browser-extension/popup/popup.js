// ================================================================
// Deus Vault — Popup script
// ================================================================

'use strict';

const DEFAULT_API = 'https://content.mugrelore.com/api';

// ── DOM refs ────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const screens = {
  loading: $('screen-loading'),
  login:   $('screen-login'),
  main:    $('screen-main'),
};

// Login
const loginEmail    = $('login-email');
const loginPassword = $('login-password');
const loginApi      = $('login-api');
const loginBtn      = $('login-btn');
const loginError    = $('login-error');

// Main
const contentBlock      = $('content-block');
const contentThumbWrap  = $('content-thumb-wrap');
const contentThumb      = $('content-thumb');
const contentTitle      = $('content-title');
const contentAuthor     = $('content-author');
const contentStatus     = $('content-status');

const actionBar         = $('action-bar');
const actionBarPending  = $('action-bar-pending');
const btnAddPending     = $('btn-add-pending');
const btnAddConsumed    = $('btn-add-consumed');
const btnMarkConsumed   = $('btn-mark-consumed');
const btnMarkAbandoned  = $('btn-mark-abandoned');

const lookupBlock   = $('lookup-block');
const lookupUrl     = $('lookup-url');
const lookupBtn     = $('lookup-btn');
const lookupError   = $('lookup-error');
const lookupResult  = $('lookup-result');
const lrTitle       = $('lr-title');
const lrAuthor      = $('lr-author');
const lrStatus      = $('lr-status');
const lrBtnPending  = $('lr-btn-pending');
const lrBtnConsumed = $('lr-btn-consumed');

const noContentBlock = $('no-content-block');

// Wishlist / product
const productBlock     = $('product-block');
const productThumbWrap = $('product-thumb-wrap');
const productThumb     = $('product-thumb');
const productTitle     = $('product-title');
const productStore     = $('product-store');
const productPrice     = $('product-price');
const productActionBar = $('product-action-bar');
const btnAddWishlist   = $('btn-add-wishlist');
const productAddedMsg  = $('product-added-msg');

const footer      = $('footer');
const footerUser  = $('footer-user');
const logoutBtn   = $('logout-btn');
const openLink    = $('open-vault-link');

// ── App state ───────────────────────────────────────────────────
let currentTab    = null;   // active Chrome tab
let ytState       = null;   // { videoId, vaultStatus, url, title } from content script
let lrMeta        = null;   // lookup result meta
let lrExisting    = null;   // existing vault item for lookup result
let productMeta   = null;   // extracted product data from content script

// ── Helpers ─────────────────────────────────────────────────────

function show(el)  { el.classList.remove('hidden'); }
function hide(el)  { el.classList.add('hidden'); }

function showScreen(name) {
  Object.values(screens).forEach(s => s.classList.add('hidden'));
  screens[name].classList.remove('hidden');
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideError(el) {
  el.classList.add('hidden');
}

function sw(type, extra = {}) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, ...extra }, (resp) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!resp?.ok) reject(new Error(resp?.error || 'Error desconocido'));
      else resolve(resp.data);
    });
  });
}

function isYouTubeWatchTab(tab) {
  return tab?.url?.includes('youtube.com/watch');
}

const PRODUCT_HOSTS = [
  'amazon.es', 'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr',
  'fnac.es', 'pccomponentes.com', 'mediamarkt.es', 'elcorteingles.es',
  'apple.com', 'ebay.es', 'ebay.com', 'zalando.es', 'zara.com',
];

function isProductTab(tab) {
  if (!tab?.url) return false;
  try {
    const host = new URL(tab.url).hostname.replace('www.', '');
    return PRODUCT_HOSTS.some(h => host === h || host.endsWith('.' + h));
  } catch (_) { return false; }
}

function formatStatus(content) {
  if (!content) return '';
  if (content.consumed) {
    const n = content.times_consumed;
    return `✅ Visto${n && n > 1 ? ` ×${n}` : ''}`;
  }
  if (content.abandoned) return '🚫 Abandonado';
  return '📋 Pendiente';
}

// ── Init ─────────────────────────────────────────────────────────

async function init() {
  showScreen('loading');

  // Load saved API URL into login form
  const stored = await chrome.storage.local.get(['apiUrl']);
  loginApi.value = stored.apiUrl || DEFAULT_API;

  // Get current auth state
  let auth;
  try { auth = await sw('GET_AUTH'); } catch (_) { auth = { loggedIn: false }; }

  // Get current tab
  try {
    [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (_) {}

  // Set vault link
  const apiUrl = stored.apiUrl || DEFAULT_API;
  const vaultUrl = apiUrl.replace('/api', '').replace(/\/$/, '');
  openLink.href = vaultUrl;

  if (!auth.loggedIn) {
    showScreen('login');
    return;
  }

  // Logged in
  footerUser.textContent = auth.user?.email || '';
  show(footer);
  show(screens.main);
  screens.loading.classList.add('hidden');

  try {
    await loadCurrentTabContent(auth);
  } catch (err) {
    if (err?.message?.includes('401') || err?.message?.toLowerCase().includes('unauthorized') || err?.message?.toLowerCase().includes('invalid')) {
      showSessionExpired();
    }
  }
}

function showSessionExpired() {
  hide(contentBlock);
  hide(actionBar);
  hide(actionBarPending);
  hide(lookupBlock);
  hide(noContentBlock);
  show(screens.main);
  const msg = document.createElement('div');
  msg.style.cssText = 'padding:16px; text-align:center; color:var(--text-muted); font-size:13px; line-height:1.6;';
  msg.innerHTML = '🔒 <strong>Sesión expirada</strong><br>El token ha caducado.<br>Inicia sesión de nuevo.';
  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.textContent = 'Iniciar sesión';
  btn.style.cssText = 'margin-top:10px; width:100%;';
  btn.addEventListener('click', () => {
    chrome.storage.local.remove(['token', 'user']);
    hide(footer);
    showScreen('login');
  });
  msg.appendChild(document.createElement('br'));
  msg.appendChild(btn);
  screens.main.innerHTML = '';
  screens.main.appendChild(msg);
}

async function loadCurrentTabContent(auth) {
  // Hide all content blocks first
  hide(contentBlock);
  hide(actionBar);
  hide(actionBarPending);
  hide(lookupBlock);
  hide(noContentBlock);
  hide(productBlock);
  hide(productActionBar);
  hide(productAddedMsg);

  if (!currentTab) {
    show(noContentBlock);
    return;
  }

  if (isYouTubeWatchTab(currentTab)) {
    await loadYouTubeState();
  } else if (isProductTab(currentTab)) {
    await loadProductState();
  } else {
    // Non-YouTube, non-product page: show lookup
    show(lookupBlock);
    if (currentTab.url && !currentTab.url.startsWith('chrome')) {
      lookupUrl.value = currentTab.url;
    }
  }
}

// ── Product state ────────────────────────────────────────────────

async function loadProductState() {
  productMeta = await getProductData();

  if (!productMeta?.title) {
    show(noContentBlock);
    return;
  }

  productTitle.textContent = productMeta.title;
  productStore.textContent = productMeta.store || '';

  if (productMeta.price != null) {
    productPrice.textContent = productMeta.price.toLocaleString('es-ES', {
      style: 'currency', currency: 'EUR', maximumFractionDigits: 2
    });
  } else {
    productPrice.textContent = 'Precio no detectado — edítalo al guardar';
  }

  if (productMeta.image_url) {
    productThumb.src = productMeta.image_url;
    show(productThumbWrap);
  } else {
    hide(productThumbWrap);
  }

  show(productBlock);
  show(productActionBar);
}

function getProductData() {
  return new Promise((resolve) => {
    if (!currentTab?.id) { resolve(null); return; }
    chrome.tabs.sendMessage(currentTab.id, { type: 'GET_PRODUCT' }, (resp) => {
      if (chrome.runtime.lastError) { resolve(null); return; }
      resolve(resp);
    });
  });
}

btnAddWishlist.addEventListener('click', async () => {
  if (!productMeta) return;
  btnAddWishlist.disabled = true;
  btnAddWishlist.textContent = '…';
  try {
    await sw('ADD_TO_WISHLIST', { product: productMeta });
    hide(productActionBar);
    show(productAddedMsg);
  } catch (err) {
    btnAddWishlist.textContent = '⚠ ' + err.message;
  } finally {
    btnAddWishlist.disabled = false;
    if (btnAddWishlist.textContent === '…') btnAddWishlist.textContent = '⭐ Añadir a Deseos';
  }
});

// ── YouTube state ────────────────────────────────────────────────

async function loadYouTubeState() {
  // Ask content script for current video state
  ytState = await getYtState();

  if (!ytState?.videoId) {
    show(noContentBlock);
    return;
  }

  // Show video info
  renderVideoBlock(ytState);
}

function getYtState() {
  return new Promise((resolve) => {
    if (!currentTab?.id) { resolve(null); return; }
    chrome.tabs.sendMessage(currentTab.id, { type: 'GET_STATE' }, (resp) => {
      if (chrome.runtime.lastError) { resolve(null); return; }
      resolve(resp);
    });
  });
}

function renderVideoBlock(state) {
  show(contentBlock);
  contentTitle.textContent = state.title || 'Vídeo de YouTube';

  const vs = state.vaultStatus;
  if (vs) {
    const author = vs.content?.author;
    if (author) {
      contentAuthor.textContent = author;
      show(contentAuthor);
    } else {
      hide(contentAuthor);
    }

    if (vs.inVault && vs.content) {
      contentStatus.textContent = formatStatus(vs.content);
      // Show thumbnail if available
      const thumb = vs.content.thumbnail || vs.content.channel_thumbnail;
      if (thumb) {
        contentThumb.src = thumb;
        show(contentThumbWrap);
      } else {
        hide(contentThumbWrap);
      }
      // Action bar
      if (vs.content.consumed || vs.content.abandoned) {
        hide(actionBar);
        hide(actionBarPending);
      } else {
        hide(actionBar);
        show(actionBarPending);
      }
    } else {
      // Not in vault
      contentStatus.textContent = '📭 No está en tu bóveda';
      hide(contentThumbWrap);
      hide(actionBarPending);
      show(actionBar);
    }
  } else {
    // Still loading status — retry once, then show error if still nothing
    contentStatus.textContent = '⏳ Comprobando…';
    hide(contentThumbWrap);
    hide(actionBar);
    hide(actionBarPending);
    setTimeout(async () => {
      ytState = await getYtState();
      if (ytState?.vaultStatus) {
        renderVideoBlock(ytState);
      } else if (ytState) {
        // Second retry failed — show session expired regardless
        showSessionExpired();
      }
    }, 1500);
  }
}

// ── YouTube action buttons ────────────────────────────────────────

btnAddPending.addEventListener('click', async () => {
  if (!ytState?.videoId) return;
  btnAddPending.disabled = true;
  try {
    await sw('ADD_PENDING', {
      videoId: ytState.videoId,
      url:     ytState.url,
      tabId:   currentTab?.id,
    });
    contentStatus.textContent = '📋 Pendiente';
    show(actionBarPending);
    hide(actionBar);
    ytState = await getYtState();
  } catch (err) {
    contentStatus.textContent = '⚠ ' + err.message;
  } finally {
    btnAddPending.disabled = false;
  }
});

btnAddConsumed.addEventListener('click', async () => {
  if (!ytState?.videoId) return;
  btnAddConsumed.disabled = true;
  try {
    await sw('ADD_CONSUMED', {
      videoId:    ytState.videoId,
      url:        ytState.url,
      existingId: ytState.vaultStatus?.content?.id ?? null,
      tabId:      currentTab?.id,
    });
    contentStatus.textContent = '✅ Visto';
    hide(actionBar);
    hide(actionBarPending);
  } catch (err) {
    contentStatus.textContent = '⚠ ' + err.message;
  } finally {
    btnAddConsumed.disabled = false;
  }
});

btnMarkConsumed.addEventListener('click', async () => {
  const contentId = ytState?.vaultStatus?.content?.id;
  if (!contentId) return;
  btnMarkConsumed.disabled = true;
  try {
    await sw('MARK_CONSUMED', { contentId, tabId: currentTab?.id });
    contentStatus.textContent = '✅ Visto';
    hide(actionBarPending);
  } catch (err) {
    contentStatus.textContent = '⚠ ' + err.message;
  } finally {
    btnMarkConsumed.disabled = false;
  }
});

btnMarkAbandoned.addEventListener('click', async () => {
  const contentId = ytState?.vaultStatus?.content?.id;
  if (!contentId) return;
  if (!confirm('¿Marcar este vídeo como abandonado?')) return;
  btnMarkAbandoned.disabled = true;
  try {
    await sw('MARK_ABANDONED', { contentId, tabId: currentTab?.id });
    contentStatus.textContent = '🚫 Abandonado';
    hide(actionBarPending);
  } catch (err) {
    contentStatus.textContent = '⚠ ' + err.message;
  } finally {
    btnMarkAbandoned.disabled = false;
  }
});

// ── Lookup (non-YouTube pages) ────────────────────────────────────

lookupBtn.addEventListener('click', () => doLookup());
lookupUrl.addEventListener('keydown', (e) => { if (e.key === 'Enter') doLookup(); });

async function doLookup() {
  const url = lookupUrl.value.trim();
  if (!url) return;
  hideError(lookupError);
  hide(lookupResult);
  lookupBtn.textContent = '…';
  lookupBtn.disabled = true;

  try {
    const result = await sw('LOOKUP_URL', { url });
    lrMeta     = result.meta;
    lrExisting = result.existing;
    renderLookupResult();
  } catch (err) {
    showError(lookupError, err.message);
  } finally {
    lookupBtn.textContent = 'Buscar';
    lookupBtn.disabled = false;
  }
}

function renderLookupResult() {
  if (!lrMeta) return;
  lrTitle.textContent = lrMeta.title || 'Sin título';
  if (lrMeta.author) {
    lrAuthor.textContent = lrMeta.author;
    show(lrAuthor);
  } else {
    hide(lrAuthor);
  }

  if (lrExisting) {
    lrStatus.textContent = formatStatus(lrExisting);
    if (lrExisting.consumed || lrExisting.abandoned) {
      lrBtnPending.style.display  = '';
      lrBtnConsumed.style.display = 'none';
    } else {
      lrBtnPending.style.display  = 'none';
      lrBtnConsumed.style.display = '';
    }
  } else {
    lrStatus.textContent = '📭 No está en tu bóveda';
    lrBtnPending.style.display  = '';
    lrBtnConsumed.style.display = '';
  }

  show(lookupResult);
}

lrBtnPending.addEventListener('click', async () => {
  if (!lrMeta) return;
  lrBtnPending.disabled = true;
  try {
    await sw('ADD_PENDING', {
      videoId: lrMeta.source_id || null,
      url:     lookupUrl.value.trim(),
      meta:    lrMeta,           // pass pre-fetched metadata to skip double lookup
      tabId:   currentTab?.id,
    });
    lrStatus.textContent = '📋 Añadido como pendiente';
    lrBtnPending.style.display  = 'none';
    lrBtnConsumed.style.display = '';
  } catch (err) {
    showError(lookupError, err.message);
  } finally {
    lrBtnPending.disabled = false;
  }
});

lrBtnConsumed.addEventListener('click', async () => {
  if (!lrMeta) return;
  lrBtnConsumed.disabled = true;
  try {
    const existingId = lrExisting?.id ?? null;
    await sw('ADD_CONSUMED', {
      videoId:    lrMeta.source_id || null,
      url:        lookupUrl.value.trim(),
      existingId,
      meta:       lrMeta,        // pass pre-fetched metadata
      tabId:      currentTab?.id,
    });
    lrStatus.textContent = '✅ Marcado como visto';
    lrBtnPending.style.display  = 'none';
    lrBtnConsumed.style.display = 'none';
  } catch (err) {
    showError(lookupError, err.message);
  } finally {
    lrBtnConsumed.disabled = false;
  }
});

// ── Login ────────────────────────────────────────────────────────

loginBtn.addEventListener('click', async () => {
  const email    = loginEmail.value.trim();
  const password = loginPassword.value;
  const apiUrl   = loginApi.value.trim() || DEFAULT_API;

  if (!email || !password) {
    showError(loginError, 'Completa email y contraseña');
    return;
  }

  hideError(loginError);
  loginBtn.textContent = 'Entrando…';
  loginBtn.disabled    = true;

  try {
    const data = await sw('LOGIN', { email, password, apiUrl });
    footerUser.textContent = data.user?.email || email;
    show(footer);
    showScreen('main');
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;
    await loadCurrentTabContent({ loggedIn: true, user: data.user });
  } catch (err) {
    showError(loginError, err.message);
  } finally {
    loginBtn.textContent = 'Entrar';
    loginBtn.disabled    = false;
  }
});

// Allow Enter on password field
loginPassword.addEventListener('keydown', (e) => { if (e.key === 'Enter') loginBtn.click(); });

// ── Logout ────────────────────────────────────────────────────────

logoutBtn.addEventListener('click', async () => {
  await sw('LOGOUT');
  hide(footer);
  showScreen('login');
});

// ── Boot ──────────────────────────────────────────────────────────

init();
