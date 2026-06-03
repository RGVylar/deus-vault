// ================================================================
// Deus Vault — Service Worker (Manifest V3)
// IMPORTANT: all chrome.* listeners MUST be registered synchronously
// at the top of this file before any async code — MV3 requirement.
// ================================================================

'use strict';

// --- Synchronous listener registration ---
chrome.runtime.onMessage.addListener(handleMessage);
chrome.notifications.onButtonClicked.addListener(handleNotifButton);
chrome.notifications.onClicked.addListener(handleNotifClick);
chrome.notifications.onClosed.addListener((notifId) => pendingNotifs.delete(notifId));

// --- In-memory state (reset when SW suspends, that's OK) ---
const pendingNotifs = new Map(); // notifId → { videoId, url, existingId, senderTabId }

// --- Constants ---
const DEFAULT_API = 'https://content.mugrelore.com/api';

// ================================================================
// Config helpers
// ================================================================

async function getConfig() {
  return chrome.storage.local.get(['token', 'apiUrl', 'user']);
}

// ================================================================
// API helpers
// ================================================================

async function apiFetch(method, path, body) {
  const { token, apiUrl } = await getConfig();
  const base = (apiUrl || DEFAULT_API).replace(/\/$/, '');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const resp = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return null;
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return resp.json();
}

const apiGet  = (path)        => apiFetch('GET', path);
const apiPost = (path, body)  => apiFetch('POST', path, body ?? null);

// ================================================================
// Badge helpers
// ================================================================

const BADGE_STATES = {
  none:     { text: '+',  color: '#f59e0b' },
  pending:  { text: '·',  color: '#7c6fe0' },
  consumed: { text: '✓',  color: '#22c55e' },
  error:    { text: '!',  color: '#ef4444' },
  clear:    { text: '',   color: '#888888' },
};

async function setBadge(tabId, state) {
  const s = BADGE_STATES[state] || BADGE_STATES.clear;
  const opts = { text: s.text };
  const colorOpts = { color: s.color };
  if (tabId) { opts.tabId = tabId; colorOpts.tabId = tabId; }
  try {
    await chrome.action.setBadgeText(opts);
    if (s.text) await chrome.action.setBadgeBackgroundColor(colorOpts);
  } catch (_) { /* tab might be closed */ }
}

// ================================================================
// Lookup + create helpers
// ================================================================

/**
 * Lookup metadata for a URL and create a content item.
 * If `meta` is provided (pre-fetched), skip the lookup call.
 * Uses /lookup/youtube for YouTube URLs, /lookup/auto for everything else.
 */
async function lookupAndCreate(videoId, url, meta = null) {
  if (!meta) {
    const isYt = url && (url.includes('youtube.com') || url.includes('youtu.be'));
    const lookupPath = isYt
      ? `/lookup/youtube?url=${encodeURIComponent(url)}`
      : `/lookup/auto?url=${encodeURIComponent(url)}`;
    meta = await apiGet(lookupPath);
  }

  const contentType = meta.suggested_content_type ||
    (url && (url.includes('youtube.com') || url.includes('youtu.be')) ? 'youtube' : 'movie');

  const content = await apiPost('/contents', {
    title:             meta.title             || 'Sin título',
    content_type:      contentType,
    url:               url                    || null,
    source_id:         meta.source_id || videoId || null,
    author:            meta.author            || null,
    thumbnail:         meta.thumbnail         || null,
    channel_thumbnail: meta.channel_thumbnail || null,
    duration_minutes:  meta.duration_minutes  || 0,
    episode_count:     meta.episode_count     || null,
    seasons:           meta.seasons           || null,
    page_count:        meta.page_count        || null,
    rating:            meta.rating            || null,
    provider:          meta.provider          || null,
    trailer_url:       meta.trailer_url       || null,
    genres:            meta.genres            || null,
    streaming_providers: meta.watch_providers?.length
      ? JSON.stringify(meta.watch_providers.map(p =>
          (p.type === 'rent' || p.type === 'buy') ? '$' + p.provider_name : p.provider_name
        ))
      : null,
  });
  return content;
}

// ================================================================
// Main message handler
// ================================================================

function handleMessage(msg, sender, sendResponse) {
  // Return true immediately to keep the channel open for async responses.
  (async () => {
    try {
      const data = await processMessage(msg, sender);
      sendResponse({ ok: true, data });
    } catch (err) {
      console.error('[DV SW] Error:', err);
      sendResponse({ ok: false, error: err.message });
    }
  })();
  return true;
}

async function processMessage(msg, sender) {
  const tabId = msg.tabId || sender.tab?.id;

  switch (msg.type) {

    // ----------------------------------------------------------
    case 'GET_AUTH': {
      const { token, user } = await getConfig();
      return { loggedIn: !!token, user: user || null };
    }

    // ----------------------------------------------------------
    case 'LOGIN': {
      const { email, password, apiUrl } = msg;
      const base = (apiUrl || DEFAULT_API).replace(/\/$/, '');
      const resp = await fetch(`${base}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!resp.ok) {
        let detail = 'Credenciales incorrectas';
        try { detail = (await resp.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const data = await resp.json();
      await chrome.storage.local.set({
        token:  data.access_token,
        user:   data.user,
        apiUrl: base,
      });
      return { user: data.user };
    }

    // ----------------------------------------------------------
    case 'LOGOUT': {
      await chrome.storage.local.remove(['token', 'user']);
      return null;
    }

    // ----------------------------------------------------------
    case 'CHECK_STATUS': {
      const { videoId } = msg;
      try {
        const item = await apiGet(`/contents/check-duplicate?source_id=${encodeURIComponent(videoId)}`);
        if (item && item.id) {
          const state = item.consumed ? 'consumed' : 'pending';
          await setBadge(tabId, state);
          return { inVault: true, content: item };
        }
        await setBadge(tabId, 'none');
        return { inVault: false, content: null };
      } catch (err) {
        // Likely unauthenticated
        await setBadge(tabId, 'clear');
        throw err;
      }
    }

    // ----------------------------------------------------------
    case 'LOOKUP_URL': {
      // Used by popup for non-YouTube pages
      const { url } = msg;
      try {
        const meta = await apiGet(`/lookup/auto?url=${encodeURIComponent(url)}`);
        // Also check if already in vault
        let existing = null;
        const sid = meta.source_id;
        if (sid) {
          try {
            const item = await apiGet(`/contents/check-duplicate?source_id=${encodeURIComponent(sid)}`);
            if (item && item.id) existing = item;
          } catch (_) {}
        }
        return { meta, existing };
      } catch (err) {
        throw new Error('No se pudo obtener información de esta URL');
      }
    }

    // ----------------------------------------------------------
    case 'ADD_PENDING': {
      const { videoId, url, meta = null } = msg;
      const content = await lookupAndCreate(videoId, url, meta);
      await setBadge(tabId, 'pending');
      return { content };
    }

    // ----------------------------------------------------------
    case 'ADD_CONSUMED': {
      const { videoId, url, existingId, meta = null, notifyTitle = null, progress = null } = msg;
      let contentId = existingId || null;

      if (!contentId) {
        // Check for existing item first to avoid duplicates (race condition
        // between auto-add at 30s and video-end firing before status updates)
        if (videoId) {
          try {
            const dup = await apiGet(`/contents/check-duplicate?source_id=${encodeURIComponent(videoId)}`);
            if (dup?.id) contentId = dup.id;
          } catch (_) {}
        }
        if (!contentId) {
          const content = await lookupAndCreate(videoId, url, meta);
          contentId = content.id;
        }
      }

      await apiPost(`/contents/${contentId}/consume`);
      if (progress != null) {
        await apiFetch('PATCH', `/contents/${contentId}`, { progress });
      }
      await setBadge(tabId, 'consumed');

      // Background tab: show a silent confirmation notification
      if (notifyTitle) {
        const short = notifyTitle.substring(0, 80);
        chrome.notifications.create(`dv-done-${Date.now()}`, {
          type:    'basic',
          iconUrl: chrome.runtime.getURL('icons/icon48.svg'),
          title:   'Deus Vault — marcado como visto ✅',
          message: `"${short}"`,
        });
      }

      return { contentId };
    }

    // ----------------------------------------------------------
    case 'MARK_CONSUMED': {
      const { contentId } = msg;
      await apiPost(`/contents/${contentId}/consume`);
      await setBadge(tabId, 'consumed');
      return { contentId };
    }

    // ----------------------------------------------------------
    case 'MARK_ABANDONED': {
      const { contentId, progress = null, notifyTitle = null } = msg;
      await apiPost(`/contents/${contentId}/abandon`);
      // Save progress % so the vault shows how far the user got
      if (progress != null) {
        await apiFetch('PATCH', `/contents/${contentId}`, { progress });
      }
      await setBadge(tabId, 'clear');
      if (notifyTitle) {
        const pct = progress != null ? ` (${progress}%)` : '';
        chrome.notifications.create(`dv-abandon-${Date.now()}`, {
          type:    'basic',
          iconUrl: chrome.runtime.getURL('icons/icon48.svg'),
          title:   'Deus Vault — abandonado 🚫',
          message: `"${notifyTitle.substring(0, 80)}"${pct}`,
        });
      }
      return { contentId };
    }

    // ----------------------------------------------------------
    case 'NOTIFY_END': {
      // Content script asks us to show a system notification (background tab)
      const { videoId, url, title, existingId } = msg;
      const notifId = `dv-end-${Date.now()}`;
      pendingNotifs.set(notifId, {
        videoId,
        url,
        existingId: existingId || null,
        senderTabId: tabId,
      });

      const shortTitle = (title || 'Vídeo de YouTube').substring(0, 80);
      await chrome.notifications.create(notifId, {
        type:    'basic',
        iconUrl: chrome.runtime.getURL('icons/icon48.svg'),
        title:   'Deus Vault — vídeo terminado',
        message: `"${shortTitle}"`,
        buttons: [
          { title: '✅ Marcar como visto' },
          { title: '＋ Solo añadir' },
        ],
      });
      return null;
    }

    // ----------------------------------------------------------
    default:
      throw new Error(`Unknown message type: ${msg.type}`);
  }
}

// ================================================================
// Notification interactions
// ================================================================

function handleNotifButton(notifId, buttonIndex) {
  const info = pendingNotifs.get(notifId);
  pendingNotifs.delete(notifId);
  chrome.notifications.clear(notifId);
  if (!info) return;

  const fakeSender = { tab: { id: info.senderTabId } };

  if (buttonIndex === 0) {
    // "Marcar como visto"
    processMessage(
      { type: 'ADD_CONSUMED', videoId: info.videoId, url: info.url, existingId: info.existingId },
      fakeSender,
    ).catch(console.error);
  } else {
    // "Solo añadir"
    processMessage(
      { type: 'ADD_PENDING', videoId: info.videoId, url: info.url },
      fakeSender,
    ).catch(console.error);
  }
}

function handleNotifClick(notifId) {
  chrome.notifications.clear(notifId);
  pendingNotifs.delete(notifId);
}
