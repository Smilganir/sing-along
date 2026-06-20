import { CHORD_SUFFIX_PATTERN } from '../constants/chordSuffixes.js';

// Derived from the canonical suffix vocabulary (already sorted longest-first so
// m7b5 beats m7 and maj7 beats maj). Keeping detection and diagram resolution
// fed by one list guarantees every highlighted chord can resolve a diagram.
const CHORD_SUFFIX = CHORD_SUFFIX_PATTERN;

const CHORD_ROOT = '[A-G][#b]?';
const CHORD_BASS = '(?:/[A-G][#b]?)?';
const CHORD_PATTERN_SOURCE = `${CHORD_ROOT}${CHORD_SUFFIX}${CHORD_BASS}`;

const CHORD_TOKEN = new RegExp(`^${CHORD_PATTERN_SOURCE}$`, 'i');
const CHORD_TOKEN_SCAN = new RegExp(`^(${CHORD_PATTERN_SOURCE})`, 'i');

const DIRECTIVE = /^\{[^}]+\}$/;
const HAS_LYRICS = /[\u0590-\u05FFa-zA-Z\u00C0-\u024F]/;
const HAS_HEBREW = /[\u0590-\u05FF]/;

export function isTabLine(line) {
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return false;
  if (/^\s*[A-Ga-g][#b]?\|/.test(trimmed)) return true;
  if (/^\s*e\|/i.test(trimmed)) return true;
  return false;
}

function normalizeChordToken(token) {
  return token
    .replace(/\(([#b]?\d+)\)/gi, '$1')
    .replace(/^[(]+|[,;)]+$/g, '')
    .replace(/\s*x\d+$/i, '');
}

function isChordToken(token) {
  const clean = normalizeChordToken(token);
  return Boolean(clean && CHORD_TOKEN.test(clean));
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
    const match = rest.match(CHORD_TOKEN_SCAN);
    if (!match) {
      return null;
    }

    chords.push(match[1]);
    index += match[1].length;
  }

  return chords.length > 0 ? chords : null;
}

/**
 * Negina stores chord columns in LTR string indices; Hebrew lyrics render RTL.
 * Mirror chord positions so LTR monospace chord rows align with RTL lyric rows.
 */
export function mirrorNeginaChordLine(chordLine, lyricLine) {
  if (!chordLine?.trim() || !lyricLine) return chordLine;

  const width = lyricLine.length;
  const slots = Array(width).fill(' ');

  for (const match of chordLine.matchAll(/\S+/g)) {
    const chord = match[0];
    const start = match.index ?? 0;
    const mirroredStart = width - 1 - start;
    if (mirroredStart < 0) continue;
    for (let offset = 0; offset < chord.length; offset += 1) {
      const index = mirroredStart + offset;
      if (index < width) {
        slots[index] = chord[offset];
      }
    }
  }

  return slots.join('').replace(/\s+$/, '');
}

export function tokenizeChordLine(line, { splitGluedChords = false } = {}) {
  if (!line) return [];

  const tokens = [];
  const parts = line.match(/(\s+|[^\s]+)/g) ?? [];

  for (const text of parts) {
    if (/^\s+$/.test(text)) {
      tokens.push({ type: 'space', text });
      continue;
    }

    if (splitGluedChords) {
      const scanned = scanChordTokens(text.trim());
      if (scanned && scanned.length > 1) {
        scanned.forEach((chord, index) => {
          if (index > 0) {
            tokens.push({ type: 'space', text: ' ' });
          }
          tokens.push({ type: 'chord', text: chord, chord });
        });
        continue;
      }
    }

    const clean = normalizeChordToken(text);
    if (isChordToken(clean)) {
      tokens.push({ type: 'chord', text, chord: clean });
    } else {
      tokens.push({ type: 'text', text });
    }
  }

  return mergeAdjacentChordFragments(tokens);
}

/** tab4u and others sometimes split m7b5 / 7b9 across tokens: "Bm7" + "b5". */
function mergeAdjacentChordFragments(tokens) {
  const out = [];

  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i];
    if (token.type !== 'chord') {
      out.push(token);
      continue;
    }

    let combined = token.chord;
    let display = token.text;
    let j = i + 1;

    while (j + 1 < tokens.length && tokens[j].type === 'space' && tokens[j + 1].type === 'text') {
      const fragment = tokens[j + 1].text;
      if (!/^[b#](?:5|9|11|13)$/.test(fragment)) break;
      const candidate = combined + fragment;
      if (!isChordToken(candidate)) break;
      combined = candidate;
      display += tokens[j].text + tokens[j + 1].text;
      j += 2;
    }

    if (combined !== token.chord) {
      out.push({ type: 'chord', text: display, chord: combined });
      i = j - 1;
      continue;
    }

    out.push(token);
  }

  return out;
}

export function isChordOnlyLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return false;

  const scanned = scanChordTokens(trimmed);
  if (scanned) {
    return true;
  }

  const tokens = trimmed.split(/\s+/).filter(Boolean);
  return tokens.length > 0 && tokens.every((token) => isChordToken(token));
}

/** ASCII-only line made entirely of chord symbols (catches odd spellings). */
function isAsciiChordLine(trimmed) {
  if (!trimmed || HAS_HEBREW.test(trimmed)) return false;
  const tokens = trimmed.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return false;
  return tokens.every((token) => isChordToken(token));
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
  if (isAsciiChordLine(trimmed)) return false;
  if (!HAS_LYRICS.test(trimmed)) return false;
  return true;
}

const NEGINA_SECTION_HEADERS = new Set(['בית', 'פזמון', 'מעבר', 'פתיחה', 'סיום', 'גשר']);

function isNeginaSectionHeader(trimmed) {
  return NEGINA_SECTION_HEADERS.has(trimmed);
}

function pushBlock(
  blocks,
  chords,
  lyrics,
  { lyricsOnly = false, showChords = true, allowChordOnly = false } = {},
) {
  if (lyricsOnly && !lyrics) return;
  if (lyricsOnly && lyrics && isAsciiChordLine(lyrics.trim())) return;
  if (!chords && !lyrics) return;
  if (showChords && !lyricsOnly && chords && !lyrics && !allowChordOnly) return;
  blocks.push({
    type: 'verse',
    chords: lyricsOnly ? null : chords,
    lyrics: lyrics || '',
  });
}

export function parseChordPro(text, { lyricsOnly = false, neginaLayout = false } = {}) {
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

    if (neginaLayout && isNeginaSectionHeader(trimmed)) {
      if (pendingChords) {
        pushBlock(blocks, pendingChords, null, { lyricsOnly, showChords, allowChordOnly: true });
        pendingChords = null;
      }
      pushBlock(blocks, null, trimmed, { lyricsOnly, showChords });
      continue;
    }

    if (isChordOnlyLine(trimmed)) {
      pendingChords = neginaLayout
        ? rawLine.replace(/\s+$/, '')
        : pendingChords
          ? `${pendingChords}   ${trimmed}`
          : trimmed;
      continue;
    }

    if (isLyricLine(trimmed)) {
      const lyrics = rawLine.replace(/\s+$/, '');
      pushBlock(blocks, pendingChords, lyrics, { lyricsOnly, showChords });
      pendingChords = null;
      continue;
    }

    if (pendingChords && !lyricsOnly) {
      pushBlock(blocks, pendingChords, null, { lyricsOnly, showChords, allowChordOnly: neginaLayout });
      pendingChords = null;
    }
  }

  if (pendingChords && !lyricsOnly) {
    pushBlock(blocks, pendingChords, null, { lyricsOnly, showChords, allowChordOnly: neginaLayout });
  }

  return blocks.filter((block) => block.lyrics || (neginaLayout && block.chords));
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

export function youtubeEmbedUrl(youtubeUrl, { origin } = {}) {
  if (!youtubeUrl) return null;
  try {
    const url = new URL(youtubeUrl);
    const id = url.searchParams.get('v') || url.pathname.split('/').pop();
    if (!id || id.length < 6) return null;
    const embed = new URL(`https://www.youtube-nocookie.com/embed/${id}`);
    if (origin) {
      embed.searchParams.set('origin', origin);
    }
    return embed.toString();
  } catch {
    return null;
  }
}
