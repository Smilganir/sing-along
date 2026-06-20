/**
 * Canonical chord-suffix vocabulary — the single source of truth for the app.
 *
 * Every other suffix table (the ChordPro detection regex, the chords-db lookup
 * map, and the all-guitar-chords URL map) is DERIVED from this list, so they
 * can never drift apart. The Python backend mirrors this file in
 * `backend/services/chord_suffixes.py`; keep the two in sync.
 *
 * Each entry:
 *   canonical : canonical label used when displaying / simplifying a chord
 *   aliases   : every sheet spelling that resolves to this suffix
 *               (the empty string '' means a bare major chord, e.g. "C")
 *   db        : @tombatossals/chords-db `suffix`, or null if absent there
 *   agc       : all-guitar-chords.com URL segment, or null if unavailable
 *   intervals : semitones from the root (used by the movable-shape generator)
 *   parent    : simpler suffix to fall back to when no exact voicing exists.
 *               Walking `parent` repeatedly always terminates at a core family
 *               ('major' / 'minor') that has a guaranteed voicing. A non-null
 *               parent means a fallback diagram is a *simplification* and must
 *               be flagged with a trailing '*' in the UI.
 */
export const CHORD_SUFFIXES = [
  // --- Triads -------------------------------------------------------------
  { canonical: 'major', aliases: ['', 'maj', 'M', 'major'], db: 'major', agc: 'major', intervals: [0, 4, 7], parent: null },
  { canonical: 'minor', aliases: ['m', 'min', 'minor'], db: 'minor', agc: 'minor', intervals: [0, 3, 7], parent: null },
  { canonical: 'dim', aliases: ['dim'], db: 'dim', agc: 'dim', intervals: [0, 3, 6], parent: 'minor' },
  { canonical: 'aug', aliases: ['aug'], db: 'aug', agc: 'aug', intervals: [0, 4, 8], parent: 'major' },
  { canonical: 'sus2', aliases: ['sus2'], db: 'sus2', agc: 'sus2', intervals: [0, 2, 7], parent: 'major' },
  { canonical: 'sus4', aliases: ['sus4', 'sus'], db: 'sus4', agc: 'sus4', intervals: [0, 5, 7], parent: 'major' },

  // --- Sixths -------------------------------------------------------------
  { canonical: '6', aliases: ['6'], db: '6', agc: '6', intervals: [0, 4, 7, 9], parent: 'major' },
  { canonical: 'm6', aliases: ['m6', 'min6'], db: 'm6', agc: 'm6', intervals: [0, 3, 7, 9], parent: 'minor' },

  // --- Sevenths -----------------------------------------------------------
  { canonical: '7', aliases: ['7', 'dom7'], db: '7', agc: '7', intervals: [0, 4, 7, 10], parent: 'major' },
  { canonical: 'maj7', aliases: ['maj7', 'M7', 'major7'], db: 'maj7', agc: 'maj7', intervals: [0, 4, 7, 11], parent: 'major' },
  { canonical: 'm7', aliases: ['m7', 'min7', 'minor7'], db: 'm7', agc: 'm7', intervals: [0, 3, 7, 10], parent: 'minor' },
  { canonical: 'm7b5', aliases: ['m7b5', 'min7b5', 'minor7b5'], db: 'm7b5', agc: 'm7b5', intervals: [0, 3, 6, 10], parent: 'dim' },
  { canonical: 'mmaj7', aliases: ['mmaj7', 'mM7', 'minmaj7'], db: 'mmaj7', agc: null, intervals: [0, 3, 7, 11], parent: 'm7' },
  { canonical: 'dim7', aliases: ['dim7'], db: 'dim7', agc: 'dim7', intervals: [0, 3, 6, 9], parent: 'dim' },

  // --- Altered dominants --------------------------------------------------
  { canonical: '7b5', aliases: ['7b5'], db: '7b5', agc: '7b5', intervals: [0, 4, 6, 10], parent: '7' },
  { canonical: '7#5', aliases: ['7#5', 'aug7', '7+5'], db: 'aug7', agc: null, intervals: [0, 4, 8, 10], parent: '7' },
  { canonical: '7b9', aliases: ['7b9'], db: '7b9', agc: '7b9', intervals: [0, 4, 7, 10, 13], parent: '7' },
  { canonical: '7#9', aliases: ['7#9'], db: '7#9', agc: null, intervals: [0, 4, 7, 10, 15], parent: '7' },
  { canonical: '7sus4', aliases: ['7sus4'], db: '7sus4', agc: '7sus4', intervals: [0, 5, 7, 10], parent: 'sus4' },
  { canonical: 'm7#5', aliases: ['m7#5'], db: null, agc: null, intervals: [0, 3, 8, 10], parent: 'm7' },
  { canonical: 'maj7b5', aliases: ['maj7b5'], db: 'maj7b5', agc: null, intervals: [0, 4, 6, 11], parent: 'maj7' },
  { canonical: 'maj7#5', aliases: ['maj7#5'], db: 'maj7#5', agc: null, intervals: [0, 4, 8, 11], parent: 'maj7' },

  // --- Ninths -------------------------------------------------------------
  { canonical: '9', aliases: ['9'], db: '9', agc: '9', intervals: [0, 4, 7, 10, 14], parent: '7' },
  { canonical: 'm9', aliases: ['m9', 'min9'], db: 'm9', agc: 'm9', intervals: [0, 3, 7, 10, 14], parent: 'm7' },
  { canonical: 'maj9', aliases: ['maj9', 'M9'], db: 'maj9', agc: null, intervals: [0, 4, 7, 11, 14], parent: 'maj7' },

  // --- Elevenths ----------------------------------------------------------
  { canonical: '11', aliases: ['11'], db: '11', agc: '11', intervals: [0, 7, 10, 14, 17], parent: '9' },
  { canonical: 'm11', aliases: ['m11', 'min11'], db: 'm11', agc: 'm11', intervals: [0, 3, 7, 10, 14, 17], parent: 'm9' },
  { canonical: 'maj11', aliases: ['maj11', 'M11'], db: 'maj11', agc: null, intervals: [0, 4, 7, 11, 14, 17], parent: 'maj9' },

  // --- Thirteenths --------------------------------------------------------
  { canonical: '13', aliases: ['13'], db: '13', agc: '13', intervals: [0, 4, 7, 10, 14, 21], parent: '9' },
  { canonical: 'm13', aliases: ['m13', 'min13'], db: null, agc: null, intervals: [0, 3, 7, 10, 14, 21], parent: 'm9' },
  { canonical: 'maj13', aliases: ['maj13', 'M13'], db: 'maj13', agc: null, intervals: [0, 4, 7, 11, 14, 21], parent: 'maj9' },

  // --- Added tones --------------------------------------------------------
  { canonical: 'add9', aliases: ['add9'], db: 'add9', agc: 'add9', intervals: [0, 4, 7, 14], parent: 'major' },
  { canonical: 'add2', aliases: ['add2'], db: null, agc: null, intervals: [0, 2, 4, 7], parent: 'major' },
  { canonical: 'add4', aliases: ['add4'], db: null, agc: null, intervals: [0, 4, 5, 7], parent: 'major' },
  { canonical: 'add11', aliases: ['add11'], db: 'add11', agc: null, intervals: [0, 4, 7, 17], parent: 'major' },
  // Bare "add" (e.g. "Cadd") is malformed but appears in real sheets — treat as major.
  { canonical: 'add', aliases: ['add'], db: 'major', agc: 'major', intervals: [0, 4, 7], parent: 'major' },
];

/** canonical suffix -> entry (fast lookup for the parent chain etc.). */
export const SUFFIX_BY_CANONICAL = new Map(CHORD_SUFFIXES.map((entry) => [entry.canonical, entry]));

function buildAliasMap(field) {
  const map = {};
  for (const entry of CHORD_SUFFIXES) {
    for (const alias of entry.aliases) {
      if (entry[field] != null && map[alias] == null) {
        map[alias] = entry[field];
      }
    }
  }
  return map;
}

/** Sheet suffix -> chords-db `suffix`. */
export const SUFFIX_TO_DB = buildAliasMap('db');

/** Sheet suffix -> all-guitar-chords.com URL segment. */
export const SUFFIX_TO_AGC = buildAliasMap('agc');

/** Sheet suffix -> canonical suffix (for simplification + display). */
export const SUFFIX_TO_CANONICAL = (() => {
  const map = {};
  for (const entry of CHORD_SUFFIXES) {
    for (const alias of entry.aliases) {
      if (map[alias] == null) map[alias] = entry.canonical;
    }
  }
  return map;
})();

/**
 * Aliases excluded from chord-token *detection* because they collide with
 * ordinary text (e.g. a bare "M" would flag "AM"/"GM" as chords). They remain
 * valid for diagram resolution if a chord is detected by other means.
 */
export const NON_DETECTABLE_ALIASES = new Set(['M']);

/**
 * All non-empty, detectable aliases, sorted longest-first so the ChordPro
 * tokenizer matches greedily (e.g. `maj7` before `maj`, `m7b5` before `m7`,
 * `min7` before `min`).
 */
export const SUFFIX_ALIASES_BY_LENGTH = CHORD_SUFFIXES.flatMap((entry) => entry.aliases)
  .filter((alias) => alias !== '' && !NON_DETECTABLE_ALIASES.has(alias))
  .sort((a, b) => b.length - a.length);

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Regex source for an optional chord suffix, derived from the canonical list.
 * Used to build the chord-token detection pattern in chordpro.js.
 */
export const CHORD_SUFFIX_PATTERN = `(?:${SUFFIX_ALIASES_BY_LENGTH.map(escapeRegExp).join('|')})?`;

/**
 * Resolve the simplification chain for a canonical suffix: returns the ordered
 * list of canonical suffixes to try, from the exact chord down to its core
 * triad. The first element is the suffix itself.
 */
export function suffixFallbackChain(canonical) {
  const chain = [];
  let current = canonical;
  const seen = new Set();
  while (current && !seen.has(current)) {
    seen.add(current);
    chain.push(current);
    const entry = SUFFIX_BY_CANONICAL.get(current);
    current = entry?.parent ?? null;
  }
  return chain;
}
