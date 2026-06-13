/**
 * Easy version: transpose the full sheet to an open key (Am / C / Em / G).
 * Computed at display time — not read from the database.
 */

import { extractChords, transposeChord, transposeSheet } from './transpose.js';

const CHORD_ROOT_SUFFIX = /^([A-G][#b]?)(.*)$/i;

export const EASY_CHORDS = new Set([
  'A',
  'Am',
  'C',
  'D',
  'Dm',
  'E',
  'Em',
  'G',
  'F',
  'A7',
  'C7',
  'D7',
  'E7',
  'G7',
]);

const MINOR_TARGETS = ['Am', 'Em', 'G'];
const MAJOR_TARGETS = ['C', 'G', 'Em'];

export function simplifyChordName(chord) {
  const match = chord.match(CHORD_ROOT_SUFFIX);
  if (!match) return chord;

  const [, root, suffix] = match;
  if (!suffix) return root;

  const lowered = suffix.toLowerCase();
  if (lowered === 'm' || lowered === 'min') return `${root}m`;
  if (lowered === 'm7' || lowered === 'min7') return `${root}m`;
  if (lowered.includes('dim')) return `${root}m`;
  if (lowered.includes('aug')) return root;
  if (lowered.startsWith('m')) return `${root}m`;
  return root;
}

function substituteChords(text, mapping) {
  const pattern =
    /\b([A-G][#b]?(?:m|maj|min|dim|aug|sus(?:2|4)?|add|maj7|m7|7|9|11|13)?(?:add(?:9|11)?)?)\b/g;
  return text.replace(pattern, (full, chord) => mapping[chord] ?? full);
}

export function simplifyChordsInSheet(text) {
  if (!text) return text;
  const mapping = Object.fromEntries(
    extractChords(text).map((chord) => [chord, simplifyChordName(chord)]),
  );
  return substituteChords(text, mapping);
}

function isMinorChord(chord) {
  const simple = simplifyChordName(chord);
  return simple.endsWith('m') && !simple.endsWith('maj');
}

function isEasyProgression(chords) {
  return chords.length > 0 && chords.every((chord) => EASY_CHORDS.has(simplifyChordName(chord)));
}

function shiftFirstChordToTarget(firstChord, target) {
  const first = simplifyChordName(firstChord);
  for (let shift = -11; shift <= 11; shift += 1) {
    if (simplifyChordName(transposeChord(first, shift)) === target) {
      return shift;
    }
  }
  return null;
}

function easyKeyTargets(firstChord) {
  return isMinorChord(firstChord) ? MINOR_TARGETS : MAJOR_TARGETS;
}

function easyNoteHe(key, { capo = null } = {}) {
  if (capo != null) {
    return `גרסה קלה — קאפו בסריג ${capo} (צורות פתוחות)`;
  }
  const labels = { Am: 'סול מ (Am)', C: 'דו מז\'ור (C)', Em: 'מי מ (Em)', G: 'סול מז\'ור (G)' };
  return `גרסה קלה — ${labels[key] ?? key}`;
}

function easyNoteEn(key, { capo = null } = {}) {
  if (capo != null) {
    return `Easy version — capo on fret ${capo} (open shapes)`;
  }
  const labels = { Am: 'Am key', C: 'C major', Em: 'Em key', G: 'G major' };
  return `Easy version — ${labels[key] ?? key}`;
}

function evaluateCandidate(work, shift) {
  const transposed = simplifyChordsInSheet(transposeSheet(work, shift));
  const chords = extractChords(transposed).map(simplifyChordName);
  return isEasyProgression(chords) ? transposed : null;
}

/**
 * @returns {{ text: string, noteHe: string, noteEn: string, key: string|null, capo: number|null, available: boolean }}
 */
export function buildEasyVersion(text, language = 'en') {
  const empty = {
    text: '',
    noteHe: '',
    noteEn: '',
    key: null,
    capo: null,
    available: false,
  };

  if (!text?.trim()) return empty;

  const work = simplifyChordsInSheet(text);
  const chords = extractChords(work);
  if (chords.length === 0) return empty;

  if (isEasyProgression(chords.map(simplifyChordName))) {
    const key = simplifyChordName(chords[0]);
    return {
      text: work,
      noteHe: easyNoteHe(key),
      noteEn: easyNoteEn(key),
      key,
      capo: null,
      available: true,
    };
  }

  const first = chords[0];
  const targets = easyKeyTargets(first);

  for (const target of targets) {
    const shift = shiftFirstChordToTarget(first, target);
    if (shift == null) continue;
    const candidate = evaluateCandidate(work, shift);
    if (candidate) {
      return {
        text: candidate,
        noteHe: easyNoteHe(target),
        noteEn: easyNoteEn(target),
        key: target,
        capo: null,
        available: true,
      };
    }
  }

  for (let capo = 1; capo < 12; capo += 1) {
    const candidate = evaluateCandidate(work, -capo);
    if (candidate) {
      return {
        text: candidate,
        noteHe: easyNoteHe(null, { capo }),
        noteEn: easyNoteEn(null, { capo }),
        key: null,
        capo,
        available: true,
      };
    }
  }

  const primary = targets[0];
  const shift = shiftFirstChordToTarget(first, primary) ?? 0;
  const fallback = simplifyChordsInSheet(transposeSheet(work, shift));
  return {
    text: fallback,
    noteHe: easyNoteHe(primary),
    noteEn: easyNoteEn(primary),
    key: primary,
    capo: null,
    available: true,
  };
}
