export function adminSongHref(songId) {
  return `#admin?song=${songId}`;
}

function normalizeRouteBase(base) {
  return base === 'library' ? 'admin' : base;
}

export function parseRouteBase(hash = window.location.hash) {
  const raw = hash.slice(1) || 'sing';
  return normalizeRouteBase(raw.split('?')[0] || 'sing');
}

export function parseAdminSongId(hash = window.location.hash) {
  const raw = hash.slice(1);
  if (!raw.startsWith('admin') && !raw.startsWith('library')) return null;
  const query = raw.includes('?') ? raw.split('?').slice(1).join('?') : '';
  const id = Number(new URLSearchParams(query).get('song'));
  return Number.isFinite(id) && id > 0 ? id : null;
}
