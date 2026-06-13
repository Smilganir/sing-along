const CHORD_TOKEN =
  /^[A-G][#b]?(?:maj7|maj|min7|min|m7|m9|m11|m13|m|sus4|sus2|sus|add9|add11|add|dim7|dim|aug7|aug|6|7|9|11|13)?(?:\/[A-G][#b]?)?$/i;

const DIRECTIVE = /^\{[^}]+\}$/;
const HAS_LYRICS = /[\u0590-\u05FFa-zA-Z\u00C0-\u024F]/;

export function isTabLine(line) {
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return false;
  if (/^\s*[A-Ga-g][#b]?\|/.test(trimmed)) return true;
  if (/^\s*e\|/i.test(trimmed)) return true;
  return false;
}

function normalizeChordToken(token) {
  return token.replace(/^[(]+|[,;)]+$/g, '').replace(/\s*x\d+$/i, '');
}

function scanChordTokens(trimmed) {
  let index = 0;
  const chords = [];

  while (index < trimmed.length) {
    if (trimmed[index] === ' ') {
      index += 1;
      continue;
    }

    const rest = trimmed.slice(index);
    const match = rest.match(
      /^([A-G][#b]?(?:maj7|maj|min7|min|m7|m9|m11|m13|m|sus4|sus2|sus|add9|add11|add|dim7|dim|aug7|aug|6|7|9|11|13)?(?:\/[A-G][#b]?)?)/i,
    );
    if (!match) {
      return null;
    }

    chords.push(match[1]);
    index += match[1].length;
  }

  return chords.length > 0 ? chords : null;
}

export function tokenizeChordLine(line) {
  if (!line) return [];

  const tokens = [];
  const parts = line.match(/(\s+|[^\s]+)/g) ?? [];

  for (const text of parts) {
    if (/^\s+$/.test(text)) {
      tokens.push({ type: 'space', text });
      continue;
    }

    const clean = normalizeChordToken(text);
    if (clean && CHORD_TOKEN.test(clean)) {
      tokens.push({ type: 'chord', text, chord: clean });
    } else {
      tokens.push({ type: 'text', text });
    }
  }

  return tokens;
}

export function isChordOnlyLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return false;

  const scanned = scanChordTokens(trimmed);
  if (scanned) {
    return true;
  }

  const tokens = trimmed.split(/\s+/);
  return tokens.every((token) => {
    const clean = normalizeChordToken(token);
    return clean && CHORD_TOKEN.test(clean);
  });
}

function normalizeText(text) {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function isSkippableLine(trimmed) {
  if (!trimmed) return false;
  if (DIRECTIVE.test(trimmed)) return true;
  if (isTabLine(trimmed)) return true;
  if (/^Intro:/i.test(trimmed)) return true;
  if (/^Heres that background/i.test(trimmed)) return true;
  if (/^\(plucking/i.test(trimmed)) return true;
  if (/^plucking$/i.test(trimmed)) return true;
  if (/^[,()]+$/.test(trimmed)) return true;
  if (/^x\d+$/i.test(trimmed)) return true;
  if (/^מעבר:/.test(trimmed)) return true;
  if (/^פתיחה:/.test(trimmed)) return true;
  if (/^סיום:/.test(trimmed)) return true;
  if (/^(Intro|Verse|Chorus|Bridge|Outro|סיום):/i.test(trimmed)) return true;
  return false;
}

function isTabLikeContent(line) {
  const trimmed = line.trim();
  if (isTabLine(trimmed)) return true;
  if (/^[A-Ga-g][#b]?\|[-\dxXp/\\|\s]+$/i.test(trimmed)) return true;
  return false;
}

function isLyricLine(trimmed) {
  if (isChordOnlyLine(trimmed)) return false;
  if (!HAS_LYRICS.test(trimmed)) return false;
  return true;
}

function pushBlock(blocks, chords, lyrics, { lyricsOnly = false, showChords = true } = {}) {
  if (lyricsOnly && !lyrics) return;
  if (!chords && !lyrics) return;
  if (showChords && !lyricsOnly && chords && !lyrics) return;
  blocks.push({
    type: 'verse',
    chords: lyricsOnly ? null : chords,
    lyrics: lyrics || '',
  });
}

export function parseChordPro(text, { lyricsOnly = false } = {}) {
  if (!text?.trim()) return [];

  const showChords = !lyricsOnly;
  const blocks = [];
  let pendingChords = null;

  for (const rawLine of normalizeText(text).split('\n')) {
    const trimmed = rawLine.trim();
    if (!trimmed) continue;

    if (isSkippableLine(trimmed)) {
      pendingChords = null;
      continue;
    }

    if (showChords && isTabLikeContent(rawLine)) {
      pendingChords = null;
      continue;
    }

    if (isChordOnlyLine(trimmed)) {
      pendingChords = pendingChords ? `${pendingChords}   ${trimmed}` : trimmed;
      continue;
    }

    if (isLyricLine(trimmed)) {
      const lyrics = rawLine.replace(/\s+$/, '');
      pushBlock(blocks, pendingChords, lyrics, { lyricsOnly, showChords });
      pendingChords = null;
      continue;
    }

    if (pendingChords && !lyricsOnly) {
      pushBlock(blocks, pendingChords, null, { lyricsOnly, showChords });
      pendingChords = null;
    }
  }

  if (pendingChords && !lyricsOnly) {
    pushBlock(blocks, pendingChords, null, { lyricsOnly, showChords });
  }

  return blocks.filter((block) => block.lyrics);
}

/** Stable hash for a lyric line — shared scroll anchor across chord/lyrics-only views. */
export function lyricAnchorHash(lyrics) {
  const normalized = (lyrics || '').trim().replace(/\s+/g, ' ');
  let hash = 5381;
  for (let i = 0; i < normalized.length; i += 1) {
    hash = ((hash << 5) + hash) ^ normalized.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

export function youtubeEmbedUrl(youtubeUrl) {
  if (!youtubeUrl) return null;
  try {
    const url = new URL(youtubeUrl);
    const id = url.searchParams.get('v') || url.pathname.split('/').pop();
    if (!id || id.length < 6) return null;
    return `https://www.youtube.com/embed/${id}`;
  } catch {
    return null;
  }
}
