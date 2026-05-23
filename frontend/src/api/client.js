const RAW_API_BASE = import.meta.env.VITE_API_BASE ?? '/api';
const API_BASE = RAW_API_BASE.replace(/\/$/, '');

export { API_BASE };

const TOKEN_KEY = 'singalong-admin-token';
export const getAdminToken = () => localStorage.getItem(TOKEN_KEY);
export const setAdminToken = (v) => localStorage.setItem(TOKEN_KEY, v);
export const clearAdminToken = () => localStorage.removeItem(TOKEN_KEY);

const readCache = new Map();
const READ_CACHE_TTL_MS = 30_000;

async function cachedGet(path, ttlMs = READ_CACHE_TTL_MS) {
  const now = Date.now();
  const hit = readCache.get(path);
  if (hit && now - hit.at < ttlMs) {
    return hit.data;
  }
  const data = await request(path);
  readCache.set(path, { data, at: now });
  return data;
}

export function invalidateReadCache(prefix = '') {
  for (const key of readCache.keys()) {
    if (!prefix || key.startsWith(prefix)) {
      readCache.delete(key);
    }
  }
}

async function request(path, options = {}) {
  const token = getAdminToken();
  const authHeaders = token ? { 'X-Admin-Token': token } : {};
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers: { ...authHeaders, ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : response.statusText;
    throw new Error(detail || 'Request failed');
  }
  return data;
}

function jsonHeaders(extra = {}) {
  return {
    'Content-Type': 'application/json',
    ...extra,
  };
}

export function getAuthMe() {
  return request('/auth/me');
}

export async function loginAdmin(password) {
  const data = await request('/auth/login', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ password }),
  });
  if (data.token) setAdminToken(data.token);
  return data;
}

export function logoutAdmin() {
  clearAdminToken();
  return request('/auth/logout', { method: 'POST' });
}

export function getAdminStatus() {
  return request('/admin/status');
}

export function getSongs({ lang, q, sort, status, ids, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (lang) params.set('lang', lang);
  if (q) params.set('q', q);
  if (sort) params.set('sort', sort);
  if (status) params.set('status', status);
  if (ids?.length) params.set('ids', ids.join(','));
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return cachedGet(`/songs?${params.toString()}`);
}

export function getSong(id) {
  return request(`/songs/${id}`);
}

export function addSong(song) {
  return request('/songs', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(song),
  });
}

export function enrichSong(id, { bustCache = false } = {}) {
  const params = bustCache ? '?bust_cache=true' : '';
  return request(`/songs/${id}/enrich${params}`, {
    method: 'POST',
  });
}

export function enrichSongFromUrl(id, sourceUrl) {
  return request(`/songs/${id}/enrich-from-url`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ source_url: sourceUrl }),
  });
}

export function saveSongSheet(id, { chordpro_full, chordpro_easy } = {}) {
  return request(`/songs/${id}/sheet`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({ chordpro_full, chordpro_easy, source_status: 'ready' }),
  });
}

export function removeSong(id) {
  return request(`/songs/${id}`, {
    method: 'DELETE',
  });
}

export function getRoomState() {
  return request('/room/state');
}

export function subscribeRoomState(onMessage, onError) {
  let source = null;
  let reconnectTimer = null;
  let closed = false;

  function connect() {
    if (closed) return;

    const token = getAdminToken();
    const streamUrl = token
      ? `${API_BASE}/room/stream?token=${encodeURIComponent(token)}`
      : `${API_BASE}/room/stream`;
    source = new EventSource(streamUrl, { withCredentials: true });

    source.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (err) {
        onError?.(err);
      }
    };

    source.onerror = () => {
      if (closed) return;
      source?.close();
      source = null;
      onError?.(new Error('Room SSE connection lost'));
      reconnectTimer = setTimeout(connect, 3000);
    };
  }

  connect();

  return function unsubscribe() {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    source?.close();
    source = null;
  };
}

export function syncRoom(songId) {
  return request('/room/sync', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ song_id: songId }),
  });
}

export function scrollRoom(scrollAnchor) {
  return request('/room/scroll', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ scroll_anchor: scrollAnchor }),
  });
}

export function getFavorites() {
  return cachedGet('/favorites', 15_000);
}

export async function addFavorite(songId) {
  const data = await request(`/favorites/${songId}`, { method: 'POST' });
  invalidateReadCache('/favorites');
  return data;
}

export async function removeFavorite(songId) {
  const data = await request(`/favorites/${songId}`, { method: 'DELETE' });
  invalidateReadCache('/favorites');
  return data;
}

export async function syncFavorites(ids) {
  const data = await request('/favorites/sync', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ ids }),
  });
  invalidateReadCache('/favorites');
  return data;
}

export function subscribeFavorites(onMessage, onError) {
  let source = null;
  let reconnectTimer = null;
  let closed = false;

  function connect() {
    if (closed) return;

    source = new EventSource(`${API_BASE}/favorites/stream`, { withCredentials: true });

    source.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (err) {
        onError?.(err);
      }
    };

    source.onerror = () => {
      if (closed) return;
      source?.close();
      source = null;
      onError?.(new Error('Favorites SSE connection lost'));
      reconnectTimer = setTimeout(connect, 3000);
    };
  }

  connect();

  return function unsubscribe() {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    source?.close();
    source = null;
  };
}
