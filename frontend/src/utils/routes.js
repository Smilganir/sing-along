export function librarySongHref(songId) {
  return `#library?song=${songId}`;
}

export function parseRouteBase(hash = window.location.hash) {
  const raw = hash.slice(1) || 'sing';
  return raw.split('?')[0] || 'sing';
}

export function parseLibrarySongId(hash = window.location.hash) {
  const raw = hash.slice(1);
  if (!raw.startsWith('library')) return null;
  const query = raw.includes('?') ? raw.split('?').slice(1).join('?') : '';
  const id = Number(new URLSearchParams(query).get('song'));
  return Number.isFinite(id) && id > 0 ? id : null;
}
