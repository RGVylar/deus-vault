// ================================================================
// Deus Vault — YouTube Content Script
// Runs on youtube.com/watch pages
// ================================================================

(function () {
  'use strict';

  if (window.__dvInjected) return;
  window.__dvInjected = true;

  // ── State ─────────────────────────────────────────────────────
  let currentVideoId    = null;
  let currentVideoTitle = '';      // updated on timeupdate (stable, pre-nav value)
  let currentCompletion = 0;       // updated on timeupdate (stable, pre-nav value)
  let vaultStatus       = null;    // { inVault, content }
  let autoAddDone       = false;
  let consumeInitiated  = false;   // prevents double-consume
  let toast             = null;

  // ── Entry point ───────────────────────────────────────────────

  init();
  window.addEventListener('yt-navigate-finish', onNavigate);

  function init() { onNavigate(); }

  // ── Navigation ────────────────────────────────────────────────

  function onNavigate() {
    const newVideoId = new URLSearchParams(location.search).get('v');

    // Leaving a video — decide what to do with it
    if (currentVideoId && currentVideoId !== newVideoId) {
      handleLeave();
    }

    if (!newVideoId || newVideoId === currentVideoId) {
      if (!newVideoId) resetState();
      return;
    }

    resetState();
    currentVideoId = newVideoId;

    removeToast();
    attachListeners();
    checkVaultStatus();
  }

  function resetState() {
    currentVideoId    = null;
    currentVideoTitle = '';
    currentCompletion = 0;
    vaultStatus       = null;
    autoAddDone       = false;
    consumeInitiated  = false;
  }

  // ── Handle leaving a video ────────────────────────────────────
  // Uses currentCompletion / currentVideoTitle captured DURING playback
  // (not from the DOM, which has already changed by the time yt-navigate-finish fires)

  function handleLeave() {
    if (consumeInitiated) return;                   // video.ended already handled it
    if (!vaultStatus?.inVault) return;              // not tracked
    if (vaultStatus.content?.consumed)   return;   // already consumed
    if (vaultStatus.content?.abandoned)  return;   // already abandoned

    const comp = currentCompletion;
    if (comp < 0.10) return;                        // too short — ignore

    const contentId    = vaultStatus.content?.id ?? null;
    const title        = currentVideoTitle;
    const isBackground = document.hidden;

    if (comp >= 0.85) {
      consumeInitiated = true;
      const pct = Math.round(comp * 100);
      autoConsume(contentId, title, isBackground, pct);
    } else {
      const pct = Math.round(comp * 100);
      chrome.runtime.sendMessage(
        { type: 'MARK_ABANDONED', contentId, progress: pct, notifyTitle: isBackground ? title : null },
        (resp) => {
          if (chrome.runtime.lastError || !resp?.ok) return;
          if (!isBackground) showBriefToast(`🚫 Abandonado al ${pct}%`);
        },
      );
    }
  }

  // ── Attach video listeners ────────────────────────────────────

  function attachListeners() {
    const tryAttach = () => {
      const v = getVideo();
      if (!v) return false;
      // Always remove first — YouTube reuses the same <video> element across
      // SPA navigations, so without this we'd accumulate duplicate listeners.
      v.removeEventListener('timeupdate',     onTimeUpdate);
      v.removeEventListener('ended',          onVideoEnded);
      v.removeEventListener('play',           onTimeUpdate);
      v.removeEventListener('loadedmetadata', onTimeUpdate);
      v.addEventListener('timeupdate',     onTimeUpdate);
      v.addEventListener('ended',          onVideoEnded);
      // Background-tab fallback: timeupdate can be throttled before first focus.
      // play + loadedmetadata fire reliably regardless of tab visibility.
      v.addEventListener('play',           onTimeUpdate);
      v.addEventListener('loadedmetadata', onTimeUpdate);
      return true;
    };

    if (!tryAttach()) {
      const obs = new MutationObserver(() => {
        if (tryAttach()) obs.disconnect();
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
  }

  // ── timeupdate — tracks completion and auto-add ───────────────

  function onTimeUpdate() {
    const v = getVideo();
    if (!v || !v.duration || v.duration === Infinity) return;
    if (v.duration < 10) return; // skip truly short clips / ad transitions

    // Keep state current so handleLeave() reads stable pre-nav values
    currentCompletion = v.currentTime / v.duration;
    currentVideoTitle = document.title.replace(/ - YouTube$/, '').trim();

    // Auto-add as pending after enough playback
    if (autoAddDone) return;
    if (vaultStatus?.inVault) { autoAddDone = true; return; } // already tracked

    // Dynamic threshold: 20% of video duration, min 5s, max 20s.
    // This way a 29s clip adds after ~6s, a 5min video after 20s.
    const threshold = Math.max(5, Math.min(20, v.duration * 0.20));
    if (v.currentTime >= threshold) {
      autoAddDone = true;
      doAutoAdd();
    }
  }

  function doAutoAdd() {
    const videoId = currentVideoId;
    const url     = location.href;
    chrome.runtime.sendMessage(
      { type: 'ADD_PENDING', videoId, url },
      (resp) => {
        if (chrome.runtime.lastError || !resp?.ok) return;
        vaultStatus = { inVault: true, content: resp.data.content };
        showBriefToast('⛧ Añadido a la bóveda');
      },
    );
  }

  // ── video ended ───────────────────────────────────────────────

  function onVideoEnded() {
    const v = getVideo();
    if (!v || v.duration < 10) return;    // ignore ad transitions
    // If the video ended naturally, count it — no % check needed.
    // The only guard: if someone seeked to the very end from < 10%
    if (currentCompletion < 0.10) return;
    if (consumeInitiated) return;         // already handled
    consumeInitiated = true;

    const existingId   = vaultStatus?.content?.id ?? null;
    const isBackground = document.hidden;
    autoConsume(existingId, currentVideoTitle, isBackground);
  }

  // ── autoConsume ───────────────────────────────────────────────

  function autoConsume(existingId, title, isBackground, progress = null) {
    const videoId = currentVideoId;
    const url     = location.href;

    if (!isBackground) showBriefToast('⏳ Marcando como visto…');

    chrome.runtime.sendMessage(
      { type: 'ADD_CONSUMED', videoId, url, existingId, progress, notifyTitle: isBackground ? title : null },
      (resp) => {
        if (chrome.runtime.lastError || !resp?.ok) {
          if (!isBackground) showBriefToast('⚠ No se pudo marcar como visto');
          return;
        }
        vaultStatus = { inVault: true, content: { ...vaultStatus?.content, consumed: true } };
        if (!isBackground) showBriefToast('✅ Marcado como visto en Deus Vault');
      },
    );
  }

  // ── Vault status check ────────────────────────────────────────

  function checkVaultStatus() {
    if (!currentVideoId) return;
    chrome.runtime.sendMessage(
      { type: 'CHECK_STATUS', videoId: currentVideoId },
      (resp) => {
        if (chrome.runtime.lastError) return;
        if (resp?.ok) vaultStatus = resp.data;
      },
    );
  }

  // ── Message handler (from popup) ─────────────────────────────

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === 'GET_STATE') {
      sendResponse({
        videoId:     currentVideoId,
        vaultStatus,
        url:         currentVideoId ? location.href : null,
        title:       currentVideoTitle || null,
        completion:  currentCompletion,
      });
    }
    return false;
  });

  // ── Helpers ───────────────────────────────────────────────────

  function getVideo() {
    return document.querySelector('#movie_player video');
  }

  // ── Toast UI ──────────────────────────────────────────────────

  function removeToast() {
    if (toast) { toast.remove(); toast = null; }
  }

  function showBriefToast(message) {
    removeToast();
    toast = buildToast(message, 3500);
  }

  function buildToast(message, autoDismissMs) {
    const el = document.createElement('div');
    el.id = 'dv-toast';

    const icon = document.createElement('div');
    icon.className = 'dv-toast-icon';
    icon.textContent = '⛧';

    const msg = document.createElement('div');
    msg.className = 'dv-toast-msg';
    msg.textContent = message;

    const close = document.createElement('button');
    close.className = 'dv-close-btn';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Cerrar');
    close.addEventListener('click', removeToast);

    el.appendChild(icon);
    el.appendChild(msg);
    el.appendChild(close);
    document.body.appendChild(el);

    requestAnimationFrame(() => el.classList.add('dv-toast-visible'));

    const timer = setTimeout(removeToast, autoDismissMs);
    const origRemove = el.remove.bind(el);
    el.remove = () => { clearTimeout(timer); origRemove(); };

    toast = el;
    return el;
  }

})();
