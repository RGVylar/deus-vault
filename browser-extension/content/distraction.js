// ================================================================
// Deus Vault — Distraction Tracker
// Runs on youtube.com (shorts), tiktok.com, x.com/twitter.com,
// instagram.com (reels). Counts active time on "junk" content and
// reports it to the service worker in batches.
// ================================================================

(function () {
  'use strict';

  if (window.__dvDistractionInjected) return;
  window.__dvDistractionInjected = true;

  const TICK_MS  = 5000;   // accounting resolution
  const FLUSH_MS = 30000;  // report to service worker every 30s
  const ACTIVITY_WINDOW_MS = 45000; // recent input keeps the session "active"

  let lastInputTs = Date.now();
  let accumulated = {}; // platform → seconds since last flush
  let newItems    = {}; // platform → distinct items viewed since last flush
  let lastItemKey = null;
  const seenItems = new Set(); // per-page-load dedupe of item counting

  // ── Platform detection ────────────────────────────────────────

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

  // Key identifying the current short/tiktok/reel, to count items viewed.
  // Twitter has no discrete items — returns null there.
  function itemKey(platform) {
    const path = location.pathname;
    let m = null;
    if (platform === 'shorts') m = path.match(/^\/shorts\/([\w-]+)/);
    if (platform === 'tiktok') m = path.match(/\/video\/(\d+)/);
    if (platform === 'reels')  m = path.match(/^\/reels?\/([\w-]+)/);
    return m ? `${platform}:${m[1]}` : null;
  }

  // ── Activity detection ────────────────────────────────────────

  function anyVideoPlaying() {
    for (const v of document.querySelectorAll('video')) {
      if (!v.paused && !v.ended && v.readyState > 2) return true;
    }
    return false;
  }

  function isActive() {
    if (document.visibilityState !== 'visible') return false;
    if (Date.now() - lastInputTs < ACTIVITY_WINDOW_MS) return true;
    // No recent input but a video is autoplaying (shorts/tiktok/reels loop)
    return anyVideoPlaying();
  }

  const markInput = () => { lastInputTs = Date.now(); };
  for (const ev of ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel']) {
    window.addEventListener(ev, markInput, { passive: true, capture: true });
  }

  // ── Accounting ────────────────────────────────────────────────

  setInterval(() => {
    const platform = currentPlatform();
    if (!platform) { lastItemKey = null; return; }

    const key = itemKey(platform);
    if (key && key !== lastItemKey && !seenItems.has(key)) {
      seenItems.add(key);
      newItems[platform] = (newItems[platform] || 0) + 1;
    }
    lastItemKey = key;

    if (isActive()) {
      accumulated[platform] = (accumulated[platform] || 0) + TICK_MS / 1000;
    }
  }, TICK_MS);

  // ── Reporting ─────────────────────────────────────────────────

  function localDate() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  function flush() {
    const platforms = new Set([...Object.keys(accumulated), ...Object.keys(newItems)]);
    const dateStr = localDate();
    const entries = [];
    for (const platform of platforms) {
      const seconds = Math.round(accumulated[platform] || 0);
      const items   = newItems[platform] || 0;
      if (seconds > 0 || items > 0) {
        entries.push({ date: dateStr, platform, seconds, items_count: items });
      }
    }
    if (!entries.length) return;
    accumulated = {};
    newItems    = {};
    try {
      chrome.runtime.sendMessage({ type: 'DISTRACTION_TICK', entries }, () => {
        // Swallow "receiving end does not exist" errors (SW asleep mid-reload)
        void chrome.runtime.lastError;
      });
    } catch (_) { /* extension context invalidated (update/reload) */ }
  }

  setInterval(flush, FLUSH_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);
})();
