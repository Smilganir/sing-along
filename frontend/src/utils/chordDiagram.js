import guitar from '@tombatossals/chords-db/lib/guitar.json';

import { API_BASE } from '../api/client.js';
import {
  SUFFIX_BY_CANONICAL,
  SUFFIX_TO_AGC,
  SUFFIX_TO_CANONICAL,
  SUFFIX_TO_DB,
  suffixFallbackChain,
} from '../constants/chordSuffixes.js';
import { FINGER_COLORS, STRING_STATUS_COLOR } from '../constants/fingerColors.js';

const FLAT_TO_SHARP = {
  Db: 'C#',
  Eb: 'D#',
  Gb: 'F#',
  Ab: 'G#',
  Bb: 'A#',
};

/** @tombatossals/chords-db root keys (not always ISO spellings). */
const ROOT_TO_DB_KEY = {
  C: 'C',
  'C#': 'Csharp',
  Db: 'Csharp',
  D: 'D',
  'D#': 'Eb',
  Eb: 'Eb',
  E: 'E',
  F: 'F',
  'F#': 'Fsharp',
  Gb: 'Fsharp',
  G: 'G',
  'G#': 'Ab',
  Ab: 'Ab',
  A: 'A',
  'A#': 'Bb',
  Bb: 'Bb',
  B: 'B',
};

const CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// Open-string chromatic indices: low E, A, D, G, B, high E
const OPEN_STRING_NOTES = [4, 9, 2, 7, 11, 4];

function normalizeChordForDiagram(chordName) {
  return (chordName || '')
    .trim()
    .split('/')[0]
    .trim()
    .replace(/\(([#b]?\d+)\)/gi, '$1');
}

function normalizeRoot(root) {
  const letter = root[0].toUpperCase();
  const acc = root.slice(1);
  if (acc === 'b' || acc === '♭') {
    return `${letter}b`;
  }
  if (acc === '#' || acc === '♯') {
    return `${letter}#`;
  }
  return letter;
}

function mapSuffix(raw, table) {
  if (!raw) return table[''];
  const key = raw.trim();
  if (table[key] != null) return table[key];
  const lower = key.toLowerCase();
  if (table[lower] != null) return table[lower];
  if (lower === 'major') return table[''];
  if (lower === 'minor') return table.m;
  return null;
}

function mapToCanonical(raw) {
  if (!raw) return SUFFIX_TO_CANONICAL[''];
  const key = raw.trim();
  if (SUFFIX_TO_CANONICAL[key] != null) return SUFFIX_TO_CANONICAL[key];
  const lower = key.toLowerCase();
  if (SUFFIX_TO_CANONICAL[lower] != null) return SUFFIX_TO_CANONICAL[lower];
  if (lower === 'major') return SUFFIX_TO_CANONICAL[''];
  if (lower === 'minor') return SUFFIX_TO_CANONICAL.m;
  return null;
}

function parseChordName(chordName) {
  const clean = normalizeChordForDiagram(chordName);
  const match = clean.match(/^([A-G][#b]?)(.*)$/i);
  if (!match) return null;
  const key = normalizeRoot(match[1]);
  const canonical = mapToCanonical(match[2]);
  const dbSuffix = mapSuffix(match[2], SUFFIX_TO_DB);
  const agcSuffix = mapSuffix(match[2], SUFFIX_TO_AGC);
  if (!canonical && !dbSuffix && !agcSuffix) return null;
  return {
    key,
    rootIdx: chromaticIndex(key),
    dbKey: ROOT_TO_DB_KEY[key] ?? null,
    canonical,
    suffix: dbSuffix,
    agcSuffix,
  };
}

function chromaticIndex(root) {
  const normalized = normalizeRoot(root);
  const sharp = FLAT_TO_SHARP[normalized] ?? normalized;
  return CHROMATIC.indexOf(sharp);
}

/**
 * Last-resort movable voicing built straight from a chord's interval set.
 * Anchors the root in the bass (low-E or A string) and, within a four-fret
 * window, picks the lowest chord tone available on each remaining string.
 * Only used when neither chords-db nor the curated generators can supply a
 * shape — i.e. a genuine backstop so a valid chord never renders blank.
 */
function buildMovableShape(chordName, rootIdx, intervals) {
  if (rootIdx < 0 || !intervals?.length) return null;

  const pitchClasses = new Set(intervals.map((i) => (rootIdx + i) % 12));

  // Prefer a low-E root unless that forces a high window; then use the A string.
  const eRootFret = (rootIdx - OPEN_STRING_NOTES[0] + 12) % 12;
  const aRootFret = (rootIdx - OPEN_STRING_NOTES[1] + 12) % 12;
  const useEString = eRootFret <= 7;
  const rootString = useEString ? 0 : 1;
  const windowStart = useEString ? eRootFret : aRootFret;

  const frets = Array(6).fill(-1);
  for (let s = rootString; s < 6; s += 1) {
    const openPc = OPEN_STRING_NOTES[s];
    let chosen = -1;
    for (let fret = windowStart; fret < windowStart + 4; fret += 1) {
      if (pitchClasses.has((openPc + fret) % 12)) {
        chosen = fret;
        break;
      }
    }
    frets[s] = chosen;
  }
  // Guarantee the root sits in the bass even if the loop preferred another tone.
  frets[rootString] = windowStart;

  const pressed = frets.filter((f) => f > 0);
  if (!pressed.length && !frets.includes(0)) return null;
  const baseFret = windowStart <= 1 ? 1 : windowStart;

  const fingers = Array(6).fill(0);
  [...frets.entries()]
    .filter(([, f]) => f > 0)
    .sort(([, a], [, b]) => a - b)
    .forEach(([idx], n) => {
      fingers[idx] = Math.min(n + 1, 4);
    });

  return { name: chordName, frets, fingers, baseFret, barres: [] };
}

function fretsStringToArray(frets) {
  if (Array.isArray(frets)) return frets;
  return String(frets).split('').map((char) => {
    if (char === 'x' || char === 'X') return -1;
    if (char === '0') return 0;
    const n = Number.parseInt(char, 10);
    return Number.isNaN(n) ? -1 : n;
  });
}

function fingersStringToArray(fingers) {
  if (Array.isArray(fingers)) return fingers;
  return String(fingers).split('').map((char) => Number.parseInt(char, 10) || 0);
}

function positionToShape(chordName, position) {
  const frets = fretsStringToArray(position.frets);
  const fingers = fingersStringToArray(position.fingers ?? '000000');
  const baseFret = position.baseFret ?? 1;
  const barres = [];

  if (position.barres) {
    const barreFret = Array.isArray(position.barres) ? position.barres[0] : position.barres;
    if (barreFret) {
      barres.push({ fret: barreFret, fromString: 6, toString: 1 });
    }
  }

  return {
    name: chordName,
    frets,
    fingers,
    baseFret,
    barres,
  };
}

/** Enharmonic db-key spellings to try (chords-db keys vary by version). */
function dbKeyCandidates(key) {
  const candidates = [];
  const direct = ROOT_TO_DB_KEY[key];
  if (direct) candidates.push(direct);
  // Try the alternate accidental spelling (e.g. D# <-> Eb, Db <-> C#).
  const sharp = FLAT_TO_SHARP[key];
  if (sharp && ROOT_TO_DB_KEY[sharp]) candidates.push(ROOT_TO_DB_KEY[sharp]);
  const flatEntry = Object.entries(FLAT_TO_SHARP).find(([, s]) => s === key);
  if (flatEntry && ROOT_TO_DB_KEY[flatEntry[0]]) candidates.push(ROOT_TO_DB_KEY[flatEntry[0]]);
  // Also try the raw key as a literal db key (newer chords-db uses "C#"/"Eb").
  candidates.push(key);
  return [...new Set(candidates.filter(Boolean))];
}

/** Find a chords-db entry for a key + db suffix, across enharmonic spellings. */
function findDbEntry(key, dbSuffix) {
  if (!dbSuffix) return null;
  for (const dbKey of dbKeyCandidates(key)) {
    const entries = guitar.chords[dbKey];
    const entry = entries?.find((item) => item.suffix === dbSuffix);
    if (entry?.positions?.length) return entry;
  }
  return null;
}

/** Prefer an open (baseFret 1) voicing; otherwise the first listed position. */
function pickPosition(entry) {
  const open = entry.positions.find((p) => (p.baseFret ?? 1) === 1);
  return open ?? entry.positions[0];
}

export function getChordsDbShape(chordName, key, dbSuffix) {
  let resolvedKey = key;
  let resolvedSuffix = dbSuffix;
  if (resolvedKey == null || resolvedSuffix == null) {
    const parsed = parseChordName(chordName);
    resolvedKey = parsed?.key ?? null;
    resolvedSuffix = parsed?.suffix ?? null;
  }
  if (!resolvedKey || !resolvedSuffix) return null;

  const entry = findDbEntry(resolvedKey, resolvedSuffix);
  if (!entry) return null;

  return positionToShape(chordName, pickPosition(entry));
}

/**
 * Splits "Chord/Bass" into {base, bass}.
 * Returns null for plain chords.
 */
function parseSlashChord(chordName) {
  const clean = (chordName || '').trim();
  const slashIdx = clean.indexOf('/');
  if (slashIdx < 1) return null;
  const base = clean.slice(0, slashIdx).trim();
  const bassRaw = clean.slice(slashIdx + 1).trim();
  if (!base || !bassRaw) return null;
  const bassMatch = bassRaw.match(/^([A-G][#b]?)/i);
  if (!bassMatch) return null;
  return { base, bass: normalizeRoot(bassMatch[1]) };
}

/** Append a trailing '*' to flag that the diagram is a simplification. */
function markPartial(shape, displayName, partial) {
  if (!shape) return null;
  if (!partial) return shape;
  return { ...shape, name: `${displayName}*`, partial: true };
}

/**
 * Core resolver for a plain (non-slash) chord. Walks the simplification chain
 * (exact suffix → … → core triad). At each level it tries, in order:
 *   1. chords-db's curated voicing (with enharmonic key fallback),
 *   2. an interval-derived movable shape as a backstop.
 * The first hit wins; anything past the first chain level is flagged partial.
 */
function resolvePlainChord(chordName, displayName = chordName) {
  const parsed = parseChordName(chordName);
  if (!parsed?.canonical) return getChordsDbShape(chordName) ?? null;

  const chain = suffixFallbackChain(parsed.canonical);
  for (let i = 0; i < chain.length; i += 1) {
    const canon = chain[i];
    const entry = SUFFIX_BY_CANONICAL.get(canon);
    const partial = i > 0;

    let shape = getChordsDbShape(chordName, parsed.key, entry?.db);
    if (!shape && entry?.intervals) {
      shape = buildMovableShape(chordName, parsed.rootIdx, entry.intervals);
    }

    if (shape) return markPartial(shape, displayName, partial);
  }
  return null;
}

/**
 * Builds a slash-chord voicing: the bass note becomes the lowest sounding
 * string (preferring an open string / low fret), with the base chord shape
 * stacked above and all strings below the bass muted.
 */
function buildSlashChordShape(chordName, baseChordName, bassRoot) {
  const bassSharp = FLAT_TO_SHARP[bassRoot] ?? bassRoot;
  const bassIdx = CHROMATIC.indexOf(bassSharp);
  if (bassIdx < 0) return null;

  // Lowest fret the bass note sits at on each string (string 0 = deepest).
  const placements = OPEN_STRING_NOTES.map((openPc, stringIdx) => ({
    stringIdx,
    fret: (bassIdx - openPc + 12) % 12,
  }));
  // Put the bass on the deepest-pitched string that is comfortable to reach:
  // widen the acceptable fret window only if no lower string qualifies. This
  // yields G on the low-E string for C/G, but the open-D string for A/D.
  let bass = null;
  for (const maxFret of [4, 7, 11]) {
    bass = placements.find((p) => p.fret <= maxFret);
    if (bass) break;
  }
  if (!bass) return null;

  const baseShape = resolvePlainChord(baseChordName);
  if (!baseShape?.frets) return null;

  const frets = Array(6).fill(-1);
  frets[bass.stringIdx] = bass.fret;
  for (let i = bass.stringIdx + 1; i < 6; i += 1) {
    frets[i] = baseShape.frets[i] ?? -1;
  }

  const pressed = frets.filter((f) => f > 0);
  const maxFret = pressed.length ? Math.max(...pressed) : 0;
  const minFret = pressed.length ? Math.min(...pressed) : 1;
  const baseFret = maxFret <= 4 ? 1 : minFret;

  const fingers = Array(6).fill(0);
  [...frets.entries()]
    .filter(([, f]) => f > 0)
    .sort(([, a], [, b]) => a - b)
    .forEach(([idx], n) => {
      fingers[idx] = Math.min(n + 1, 4);
    });

  return { name: chordName, frets, fingers, baseFret, barres: [] };
}

export function getLocalChordShape(chordName) {
  const slash = parseSlashChord(chordName);
  if (slash) {
    return (
      buildSlashChordShape(chordName, slash.base, slash.bass) ??
      // Fall back to the base chord's shape, still labelled with the bass.
      markPartial(resolvePlainChord(slash.base, chordName), chordName, true)
    );
  }
  return resolvePlainChord(chordName);
}

/**
 * True when we should render our own diagram instead of fetching an AGC SVG:
 * slash chords, our curated maj7/m7b5 voicings, and any chord AGC can't draw.
 */
export function usesLocalDiagram(chordName) {
  if (parseSlashChord(chordName)) return true;
  const parsed = parseChordName(chordName);
  if (!parsed) return false;
  if (parsed.canonical === 'maj7' || parsed.canonical === 'm7b5') return true;
  return !parsed.agcSuffix;
}

export function chordDiagramApiUrl(chordName) {
  return `${API_BASE}/chords/diagram?chord=${encodeURIComponent(chordName)}&v=9`;
}

const FRET_LABEL_Y = { 61: 56, 101: 96, 141: 136, 181: 176 };
const AXIS_LABEL_FILL = '#e2e8f0';
const AGC_SHAPE_RE = /<(circle|rect)\s[^>]*\/>/g;
const AGC_FINGER_NUM_TEXT_RE =
  /<text x='(\d+)' y='(\d+)' font-size='14' font-family='(?:Arial|Heebo)' fill='black'([^>]*)>([1-4])<\/text>/g;
const AGC_MUTE_TEXT_RE =
  /<text x='(\d+)' y='26' font-size='20' font-family='Arial' fill='[^']*'>X<\/text>/g;

const FINGER_NUMBER_TEXT_RE =
  /<text x='(\d+)' y='(\d+)' font-size='14' font-family='(?:Arial|Heebo)' fill='black'>(\d)<\/text>/g;

function parseAgcFingerLabels(svg) {
  const labels = [];
  for (const match of svg.matchAll(AGC_FINGER_NUM_TEXT_RE)) {
    const centered = /text-anchor='middle'/.test(match[3]);
    labels.push({
      x: centered ? Number(match[1]) : Number(match[1]) + 4,
      y: centered ? Number(match[2]) : Number(match[2]) - 5,
      digit: Number(match[4]),
    });
  }
  return labels;
}

function parseAgcShape(tag) {
  if (/width='150'\s+height='160'/.test(tag) || /height='160'\s+width='150'/.test(tag)) {
    return null;
  }

  if (tag.startsWith('<circle')) {
    const cx = Number(tag.match(/cx='(\d+)'/)?.[1]);
    const cy = Number(tag.match(/cy='(\d+)'/)?.[1]);
    const r = Number(tag.match(/r='(\d+)'/)?.[1] ?? 0);
    if (Number.isNaN(cx) || Number.isNaN(cy)) return null;
    if (r <= 8 && cy <= 25) return { kind: 'open', cx, cy, r };
    if (r >= 12 && cy >= 40) return { kind: 'finger', cx, cy, r };
    return null;
  }

  const x = Number(tag.match(/x='(\d+)'/)?.[1]);
  const y = Number(tag.match(/y='(\d+)'/)?.[1]);
  const width = Number(tag.match(/width='(\d+)'/)?.[1]);
  const height = Number(tag.match(/height='(\d+)'/)?.[1]);
  if ([x, y, width, height].some(Number.isNaN)) return null;
  if (height >= 26 && height <= 30 && width >= 20 && width <= 120) {
    return { kind: 'barre', cx: x + width / 2, cy: y + height / 2, r: 0 };
  }
  return null;
}

function nearestAgcFingerLabel(labels, cx, cy, maxDistance = 24) {
  let best = null;
  let bestDistance = maxDistance;
  for (const label of labels) {
    const distance = Math.hypot(label.x - cx, label.y - cy);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = label;
    }
  }
  return best;
}

function setAgcFill(tag, fillColor) {
  if (/fill='/.test(tag)) {
    return tag.replace(/fill='[^']+'/, `fill='${fillColor}'`);
  }
  return tag.replace(/\/>/, ` fill='${fillColor}'/>`);
}

function setAgcStroke(tag, strokeColor, strokeWidth = '2') {
  let next = tag.replace(/stroke='[^']+'/, `stroke='${strokeColor}'`);
  if (!/stroke='/.test(next)) {
    next = next.replace(/\/>/, ` stroke='${strokeColor}' stroke-width='${strokeWidth}'/>`);
  } else if (!/stroke-width='/.test(next)) {
    next = next.replace(/\/>/, ` stroke-width='${strokeWidth}'/>`);
  }
  return next;
}

function styleAgcOpenStringMarker(tag) {
  return setAgcStroke(setAgcFill(tag, STRING_STATUS_COLOR), 'none', '0');
}

function styleAgcFingerShape(tag, fillColor) {
  return setAgcStroke(setAgcFill(tag, fillColor), 'white');
}

function styleAgcMuteMarkers(svg) {
  return svg.replace(
    AGC_MUTE_TEXT_RE,
    `<text x='$1' y='26' font-size='20' font-family='Arial' fill='${STRING_STATUS_COLOR}'>X</text>`,
  );
}

function recolorAgcFingerShapes(svg) {
  const labels = parseAgcFingerLabels(svg);

  return svg.replace(AGC_SHAPE_RE, (tag) => {
    const shape = parseAgcShape(tag);
    if (!shape) return tag;

    if (shape.kind === 'open') {
      return styleAgcOpenStringMarker(tag);
    }

    if (shape.kind === 'barre') {
      return styleAgcFingerShape(tag, FINGER_COLORS[1]);
    }

    const label = nearestAgcFingerLabel(labels, shape.cx, shape.cy);
    const fillColor = label ? FINGER_COLORS[label.digit] : FINGER_COLORS[2];
    return styleAgcFingerShape(tag, fillColor);
  });
}

function isFretAxisLabel(tag) {
  return /\bx=(['"])20\1/.test(tag);
}

function isStringAxisLabel(tag) {
  return /\by=(['"])221\1/.test(tag);
}

/** Style all-guitar-chords SVGs for the dark popover (also applied server-side). */
export function adaptAgcSvgForDarkBg(svg) {
  let out = svg.replace(/fill='#e1dce2'/g, "fill='#243047'");
  out = recolorAgcFingerShapes(out);
  out = styleAgcMuteMarkers(out);
  out = out
    .replace(/stroke='black'/g, "stroke='#94a3b8'")
    .replace(
      /<svg\s+width=['"]230['"]\s+height=['"]230['"]/,
      "<svg width='230' height='250' viewBox='0 0 230 250' overflow='visible'",
    );

  out = out.replace(FINGER_NUMBER_TEXT_RE, (_match, x, y, digit) => {
    const cx = Number(x) + 4;
    const cy = Number(y) - 5;
    return `<text x='${cx}' y='${cy}' font-size='14' font-family='Heebo' fill='black' text-anchor='middle' dominant-baseline='middle'>${digit}</text>`;
  });

  out = out.replace(/<text[^>]*>/g, (tag) => {
    const fretLabel = isFretAxisLabel(tag);
    const stringLabel = isStringAxisLabel(tag);
    if (!fretLabel && !stringLabel) return tag;

    let next = tag.replace(/<text/, '<text class="agc-axis-label"');
    next = next.replace(/fill=(['"])(?:black|#000(?:000)?)\1/gi, `fill=$1${AXIS_LABEL_FILL}$1`);
    if (!/fill=/.test(next)) {
      next = next.replace(/<text/, `<text fill='${AXIS_LABEL_FILL}'`);
    }

    if (stringLabel) {
      next = next
        .replace(/\by=(['"])221\1/, "y=$1228$1 dominant-baseline='middle'")
        .replace(/\btext-anchor=(['"])middle\1/, "text-anchor=$1middle$1");
    }

    if (fretLabel) {
      next = next.replace(/\by=(['"])(\d+)\1/g, (match, quote, y) => {
        const nudged = FRET_LABEL_Y[Number(y)];
        return nudged != null ? `y=${quote}${nudged}${quote}` : match;
      });
      if (!/dominant-baseline=/.test(next)) {
        next = next.replace(/>$/, " dominant-baseline='middle'>");
      }
    }

    return next;
  });

  return out;
}

export function hasDiagramSupport(chordName) {
  return Boolean(parseChordName(chordName));
}

export function getAgcSuffix(chordName) {
  return parseChordName(chordName)?.agcSuffix ?? null;
}

export function buildAgcSvgUrl(chordName) {
  const parsed = parseChordName(chordName);
  if (!parsed?.agcSuffix) return null;

  const letter = parsed.key[0].toLowerCase();
  const segment = parsed.key.includes('#') ? `${letter}_sharp` : letter;
  return `https://www.all-guitar-chords.com/chords/img/guitar-chord-${segment}-${parsed.agcSuffix}-1.svg`;
}

/** Same-origin proxy for AGC SVGs (Vite dev/preview); avoids CORS when API is stale. */
export function buildAgcProxyUrl(chordName) {
  const upstream = buildAgcSvgUrl(chordName);
  if (!upstream) return null;
  const path = upstream.replace('https://www.all-guitar-chords.com', '');
  return `/agc-proxy${path}`;
}
