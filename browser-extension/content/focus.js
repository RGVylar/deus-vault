// ================================================================
// Deus Vault — Focus Mode
// Blocks the social feeds (YouTube Shorts, TikTok, Twitter/X,
// Instagram Reels) while a focus session is running.
//
// A session is just an end timestamp in chrome.storage.local, so it
// survives closing the tab, quitting the browser, restarting the PC
// and the service worker being suspended.
//
// There is deliberately NO way to end a session early from here.
// ================================================================

(function () {
  'use strict';

  if (window.__dvFocusInjected) return;
  window.__dvFocusInjected = true;

  const TICK_MS    = 500;   // countdown refresh + media re-pause
  const OVERLAY_ID = 'dv-focus-overlay';

  let focusUntil = 0;       // ms epoch; 0 = no session
  let overlay    = null;
  let timeEl     = null;
  let observer   = null;

  // ── Platform detection (same classification as distraction.js) ──

  function currentPlatform() {
    const host = location.hostname.replace(/^www\./, '');
    const path = location.pathname;
    if (host === 'youtube.com' || host === 'm.youtube.com') {
      return path.startsWith('/shorts/') ? 'shorts' : null;
    }
    if (host === 'tiktok.com' || host.endsWith('.tiktok.com')) return 'tiktok';
    if (host === 'x.com' || host === 'twitter.com' || host.endsWith('.twitter.com')) return 'twitter';
    if (host === 'instagram.com' || host.endsWith('.instagram.com')) {
      return (path.startsWith('/reels') || path.startsWith('/reel/')) ? 'reels' : null;
    }
    return null;
  }

  const PLATFORM_LABEL = {
    shorts:  'YouTube Shorts',
    tiktok:  'TikTok',
    twitter: 'Twitter / X',
    reels:   'Instagram Reels',
  };

  // ── Helpers ─────────────────────────────────────────────────────

  const remaining = () => Math.max(0, focusUntil - Date.now());
  const isActive  = () => remaining() > 0;

  function fmtClock(ms) {
    const total = Math.ceil(ms / 1000);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const p = (n) => String(n).padStart(2, '0');
    return h > 0 ? `${h}:${p(m)}:${p(s)}` : `${p(m)}:${p(s)}`;
  }

  // Silence anything already playing behind the overlay.
  function killMedia() {
    for (const el of document.querySelectorAll('video, audio')) {
      try {
        if (!el.paused) el.pause();
        el.muted = true;
      } catch (_) { /* cross-origin or detached node */ }
    }
  }

  // ── Overlay ─────────────────────────────────────────────────────

  function buildOverlay(platform) {
    const root = document.createElement('div');
    root.id = OVERLAY_ID;

    const card = document.createElement('div');
    card.className = 'dv-focus-card';

    const ico = document.createElement('div');
    ico.className = 'dv-focus-ico';
    ico.textContent = '🔒';

    const title = document.createElement('div');
    title.className = 'dv-focus-title';
    title.textContent = 'Modo concentración';

    const sub = document.createElement('div');
    sub.className = 'dv-focus-sub';
    sub.textContent = `${PLATFORM_LABEL[platform] || 'Esta página'} está bloqueado`;

    timeEl = document.createElement('div');
    timeEl.className = 'dv-focus-time';
    timeEl.textContent = fmtClock(remaining());

    const label = document.createElement('div');
    label.className = 'dv-focus-label';
    label.textContent = 'restante';

    const note = document.createElement('div');
    note.className = 'dv-focus-note';
    note.textContent = 'La sesión no se puede cancelar. Vuelve al trabajo.';

    card.append(ico, title, sub, timeEl, label, note);
    root.appendChild(card);
    return root;
  }

  // The overlay lives on <html>, not <body>: it has to exist at
  // document_start (before <body>) and survive SPA route changes
  // that replace the whole body subtree.
  function mount(platform) {
    if (overlay && overlay.isConnected) return;
    overlay = buildOverlay(platform);
    document.documentElement.appendChild(overlay);
    document.documentElement.classList.add('dv-focus-locked');

    // Re-attach if the page (or anyone else) rips the overlay out.
    if (!observer) {
      observer = new MutationObserver(() => {
        if (isActive() && currentPlatform() && overlay && !overlay.isConnected) {
          document.documentElement.appendChild(overlay);
        }
      });
      observer.observe(document.documentElement, { childList: true });
    }
  }

  function unmount() {
    if (observer) { observer.disconnect(); observer = null; }
    if (overlay) { overlay.remove(); overlay = null; }
    timeEl = null;
    document.documentElement.classList.remove('dv-focus-locked');
  }

  // ── Main loop ───────────────────────────────────────────────────

  function apply() {
    const platform = currentPlatform();

    if (!isActive() || !platform) {
      if (overlay) unmount();
      return;
    }

    mount(platform);
    if (timeEl) timeEl.textContent = fmtClock(remaining());
    killMedia();
  }

  // ── Session state ───────────────────────────────────────────────

  try {
    chrome.storage.local.get('focusUntil', (data) => {
      if (chrome.runtime.lastError) return;
      focusUntil = Number(data?.focusUntil) || 0;
      apply();
    });

    // Starting a session applies instantly to tabs already open.
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== 'local' || !changes.focusUntil) return;
      focusUntil = Number(changes.focusUntil.newValue) || 0;
      apply();
    });
  } catch (_) { /* extension context invalidated (update/reload) */ }

  setInterval(apply, TICK_MS);
})();
