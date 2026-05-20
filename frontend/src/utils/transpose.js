/** Client-side port of backend/services/easy_chords.py transpose helpers. */

const CHORD_PATTERN =
  /\b([A-G][#b]?(?:m|maj|min|dim|aug|sus(?:2|4)?|add|maj7|m7|7|9|11|13)?(?:add(?:9|11)?)?)\b/g;

const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

const FLAT_ALIASES = {
  Db: 'C#',
  Eb: 'D#',
  Gb: 'F#',
  Ab: 'G#',
  Bb: 'A#',
  Cb: 'B',
  Fb: 'E',
};

const SHARP_TO_FLAT = Object.fromEntries(
  Object.entries(FLAT_ALIASES).map(([flat, sharp]) => [sharp, flat]),
);

export function extractChords(text) {
  const found = [];
  const seen = new Set();

  for (const line of text.split('\n')) {
    if (line.includes('|')) continue;
    const re = new RegExp(CHORD_PATTERN.source, 'g');
    for (const match of line.matchAll(re)) {
      const chord = match[1];
      if (!seen.has(chord)) {
        seen.add(chord);
        found.push(chord);
      }
    }
  }

  return found;
}

export function transposeChord(chord, semitones) {
  const match = chord.match(/^([A-G][#b]?)(.*)$/);
  if (!match) return chord;

  const [, root, suffix] = match;
  const normalized = FLAT_ALIASES[root] ?? root;
  const index = NOTES.indexOf(normalized);
  if (index === -1) return chord;

  const newIndex = (index + semitones) % 12;
  const normalizedNote = NOTES.at(newIndex);
  const preferFlat = root.toLowerCase().includes('b');
  const newRoot =
    preferFlat && SHARP_TO_FLAT[normalizedNote]
      ? SHARP_TO_FLAT[normalizedNote]
      : normalizedNote;

  return `${newRoot}${suffix}`;
}

export function transposeSheet(text, semitones) {
  if (!text || semitones === 0) return text;

  const mapping = Object.fromEntries(
    extractChords(text).map((chord) => [chord, transposeChord(chord, semitones)]),
  );

  let result = text;
  for (const [oldChord, newChord] of Object.entries(mapping).sort(
    (a, b) => b[0].length - a[0].length,
  )) {
    result = result.replace(new RegExp(`\\b${escapeRegExp(oldChord)}\\b`, 'g'), newChord);
  }

  return result;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
