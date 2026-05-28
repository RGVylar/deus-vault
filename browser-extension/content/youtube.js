// ================================================================
// Deus Vault — YouTube Content Script
// Runs on youtube.com/watch pages
// ================================================================

(function () {
  'use strict';

  // Avoid re-injecting if already running (extension reload edge case)
  if (window.__dvInjected) return;
  window.__dvInjected = true;

  // ── State ─────────────────────────────────────────────────────
  let currentVideoId  = null;   // YouTube video ID currently open
  let vaultStatus     = null;   // { inVault: bool, content: ContentOut|null }
  let autoAddDone     = false;  // true once we've auto-added this video
  let autoAddListened = false;  // whether we attached the timeupdate listener
  let prevVideoId     = null;   // video ID we were on before navigation
  let prevCompletion  = 0;      // completion % when we navigated away
  let toast           = null;   // current toast DOM element

  // ── Entry point ───────────────────────────────────────────────

  init();
  window.addEventListener('yt-navigate-finish', onNavigate);

  function init() {
    onNavigate();
  }

  // ── Navigation handler ────────────────────────────────────────

  function onNavigate() {
    const params   = new URLSearchParams(location.search);
    const newVideoId = params.get('v');

    // Navigating away from a video without finishing it?
    if (currentVideoId && currentVideoId !== newVideoId) {
      const comp = getCompletion();
      prevVideoId    = currentVideoId;
      prevCompletion = comp;
      // Only ask if: in vault as pending AND watched 20–85%
      if (
        vaultStatus?.inVault &&
        !vaultStatus.content?.consumed &&
        comp >= 0.20 &&
        comp < 0.85
      ) {
        showAbandonToast(comp, vaultStatus.content.id);
      }
    }

    if (!newVideoId) {
      currentVideoId = null;
      vaultStatus    = null;
      autoAddDone    = false;
      autoAddListened = false;
      return;
    }

    if (newVideoId === currentVideoId) return;

    currentVideoId  = newVideoId;
    vaultStatus     = null;
    autoAddDone     = false;
    autoAddListened = false;

    removeToast();
    attachVideoEndListener();
    attachAutoAddListener();
    checkVaultStatus();
  }

  // ── Video element helpers ─────────────────────────────────────

  function getVideo() {
    return document.querySelector('#movie_player video');
  }

  function getCompletion() {
    const v = getVideo();
    if (!v || !v.duration || v.duration === Infinity) return 0;
    return v.currentTime / v.duration;
  }

  // ── Vault status check ────────────────────────────────────────

  function checkVaultStatus() {
    if (!currentVideoId) return;
    chrome.runtime.sendMessage(
      { type: 'CHECK_STATUS', videoId: currentVideoId },
      (resp) => {
        if (chrome.runtime.lastError) return; // SW not available
        if (resp?.ok) vaultStatus = resp.data;
      },
    );
  }

  // ── Auto-add as pending (after 30s of actual playback) ────────

  function attachAutoAddListener() {
    if (autoAddListened) return;

    // Use the video's timeupdate — fires during playback even in bg tabs
    // and reflects real video time (not wall clock), so throttling doesn't matter.
    const tryAttach = () => {
      const v = getVideo();
      if (!v) return false;
      v.addEventListener('timeupdate', onTimeUpdate);
      autoAddListened = true;
      return true;
    };

    if (!tryAttach()) {
      // Video element not in DOM yet — wait for it
      const obs = new MutationObserver(() => {
        if (tryAttach()) obs.disconnect();
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
  }

  function onTimeUpdate() {
    if (autoAddDone) return;
    if (vaultStatus?.inVault) { autoAddDone = true; return; } // already tracked
    const v = getVideo();
    if (!v) return;
    if (v.duration && v.duration < 30) return; // skip very short clips / ads
    if (v.currentTime >= 30 || getCompletion() >= 0.15) {
      autoAddDone = true; // set immediately to prevent duplicate calls
      doAutoAdd();
    }
  }

  function doAutoAdd() {
    chrome.runtime.sendMessage(
      { type: 'ADD_PENDING', videoId: currentVideoId, url: location.href },
      (resp) => {
        if (chrome.runtime.lastError || !resp?.ok) return;
        vaultStatus = { inVault: true, content: resp.data.content };
        showBriefToast('⛧ Añadido a la bóveda');
      },
    );
  }

  // ── Video ended detection ─────────────────────────────────────

  function attachVideoEndListener() {
    const tryAttach = () => {
      const v = getVideo();
      if (!v) return false;
      // Remove first to avoid duplicate listeners on SPA navigation
      v.removeEventListener('ended', onVideoEnded);
      v.addEventListener('ended', onVideoEnded);
      return true;
    };

    if (!tryAttach()) {
      const obs = new MutationObserver(() => {
        if (tryAttach()) obs.disconnect();
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
  }

  function onVideoEnded() {
    const v = getVideo();
    // Ignore: ads (< 30s), or if user seeked to the end without really watching
    if (!v || v.duration < 30) return;
    if (getCompletion() < 0.85) return;

    const title      = document.title.replace(/ - YouTube$/, '').trim();
    const existingId = vaultStatus?.content?.id ?? null;

    if (document.hidden) {
      // Pestaña en segundo plano → notificación del sistema
      chrome.runtime.sendMessage({
        type:       'NOTIFY_END',
        videoId:    currentVideoId,
        url:        location.href,
        title,
        existingId,
      });
    } else {
      // Pestaña activa → toast in-page
      showEndToast(existingId);
    }
  }

  // ── Message handler (from popup) ─────────────────────────────

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === 'GET_STATE') {
      sendResponse({
        videoId: currentVideoId,
        vaultStatus,
        url:   currentVideoId ? location.href : null,
        title: currentVideoId
          ? document.title.replace(/ - YouTube$/, '').trim()
          : null,
      });
    }
    return false;
  });

  // ── Toast UI ──────────────────────────────────────────────────

  function removeToast() {
    if (toast) {
      toast.remove();
      toast = null;
    }
  }

  function showBriefToast(message) {
    removeToast();
    toast = buildToast(message, [], 3500);
  }

  function showEndToast(existingId) {
    removeToast();
    const videoId = currentVideoId;
    const url     = location.href;

    toast = buildToast(
      '¿Qué hacemos con este vídeo?',
      [
        {
          label:   '✅ Marcar como visto',
          primary: true,
          onClick() {
            removeToast();
            chrome.runtime.sendMessage(
              { type: 'ADD_CONSUMED', videoId, url, existingId },
              (resp) => {
                if (!resp?.ok) return;
                vaultStatus = { inVault: true, content: { ...vaultStatus?.content, consumed: true } };
                showBriefToast('✅ Marcado como visto');
              },
            );
          },
        },
        {
          label: '＋ Pendiente',
          onClick() {
            removeToast();
            if (vaultStatus?.inVault) {
              showBriefToast('📋 Ya estaba en la bóveda');
              return;
            }
            chrome.runtime.sendMessage(
              { type: 'ADD_PENDING', videoId, url },
              (resp) => {
                if (!resp?.ok) return;
                vaultStatus = { inVault: true, content: resp.data.content };
                showBriefToast('⛧ Añadido como pendiente');
              },
            );
          },
        },
      ],
      12000,
    );
  }

  function showAbandonToast(completion, contentId) {
    removeToast();
    const pct = Math.round(completion * 100);

    toast = buildToast(
      `Saliste al ${pct}% — ¿qué hacemos?`,
      [
        {
          label: '📋 Dejar pendiente',
          onClick() { removeToast(); },
        },
        {
          label: '🚫 Abandonar',
          onClick() {
            removeToast();
            if (contentId) {
              chrome.runtime.sendMessage({ type: 'MARK_ABANDONED', contentId });
              vaultStatus = { ...vaultStatus, content: { ...vaultStatus?.content, abandoned: true } };
            }
          },
        },
      ],
      10000,
    );
  }

  /**
   * Creates and appends a toast element.
   * @param {string}   message        Main text
   * @param {Array}    buttons        [{ label, primary?, onClick }]
   * @param {number}   autoDismissMs  Auto-hide after this many ms
   * @returns {HTMLElement}
   */
  function buildToast(message, buttons, autoDismissMs) {
    const el = document.createElement('div');
    el.id = 'dv-toast';

    const icon = document.createElement('div');
    icon.className = 'dv-toast-icon';
    icon.textContent = '⛧';

    const msg = document.createElement('div');
    msg.className = 'dv-toast-msg';
    msg.textContent = message;

    const actions = document.createElement('div');
    actions.className = 'dv-toast-actions';

    buttons.forEach((btn) => {
      const b = document.createElement('button');
      b.className = 'dv-btn' + (btn.primary ? ' dv-btn-primary' : '');
      b.textContent = btn.label;
      b.addEventListener('click', btn.onClick);
      actions.appendChild(b);
    });

    const close = document.createElement('button');
    close.className = 'dv-close-btn';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Cerrar');
    close.addEventListener('click', removeToast);
    actions.appendChild(close);

    el.appendChild(icon);
    el.appendChild(msg);
    el.appendChild(actions);
    document.body.appendChild(el);

    // Animate in on next frame
    requestAnimationFrame(() => el.classList.add('dv-toast-visible'));

    // Auto-dismiss
    const timer = setTimeout(removeToast, autoDismissMs);

    // Cleanup timer if removed externally
    const origRemove = el.remove.bind(el);
    el.remove = () => { clearTimeout(timer); origRemove(); };

    toast = el;
    return el;
  }

})();
