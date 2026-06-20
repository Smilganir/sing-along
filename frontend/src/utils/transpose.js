/** Client-side port of backend/services/easy_chords.py transpose helpers. */

import { CHORD_SUFFIX_PATTERN } from '../constants/chordSuffixes.js';

export const CHORD_PATTERN = new RegExp(
  `\\b([A-G][#b]?${CHORD_SUFFIX_PATTERN}(?:/[A-G][#b]?)?)\\b`,
  'g',
);

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
  if (chord.includes('/')) {
    const slashIdx = chord.indexOf('/');
    const base = chord.slice(0, slashIdx);
    const bass = chord.slice(slashIdx + 1);
    return `${transposeChord(base, semitones)}/${transposeChord(bass, semitones)}`;
  }

  const match = chord.match(/^([A-G][#b]?)(.*)$/);
  if (!match) return chord;

  const [, root, suffix] = match;
  const normalized = FLAT_ALIASES[root] ?? root;
  const index = NOTES.indexOf(normalized);
  if (index === -1) return chord;

  const newIndex = ((index + semitones) % 12 + 12) % 12;
  const note = NOTES[newIndex];
  const preferFlat = root.toLowerCase().includes('b');
  const newRoot =
    preferFlat && note.includes('#') && SHARP_TO_FLAT[note]
      ? SHARP_TO_FLAT[note]
      : note;

  return `${newRoot}${suffix}`;
}

function substituteChords(text, mapping) {
  return text.replace(new RegExp(CHORD_PATTERN.source, 'g'), (full, chord) => mapping[chord] ?? full);
}

export function transposeSheet(text, semitones) {
  if (!text || semitones === 0) return text;

  const mapping = Object.fromEntries(
    extractChords(text).map((chord) => [chord, transposeChord(chord, semitones)]),
  );

  return substituteChords(text, mapping);
}
