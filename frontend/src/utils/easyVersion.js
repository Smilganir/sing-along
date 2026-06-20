/**
 * Easy version: transpose the full sheet to the most convenient open key.
 * Computed at display time — not read from the database.
 */

import { simplifyChordToTriad } from '../constants/chordSuffixes.js';
import { CHORD_PATTERN, extractChords, transposeSheet } from './transpose.js';

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
const KNOWN_KEY_LABELS = new Set(['Am', 'C', 'Em', 'G']);

export function simplifyChordName(chord) {
  return simplifyChordToTriad(chord);
}

function substituteChords(text, mapping) {
  return text.replace(new RegExp(CHORD_PATTERN.source, 'g'), (full, chord) => mapping[chord] ?? full);
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

function easyKeyTargets(firstChord) {
  return isMinorChord(firstChord) ? MINOR_TARGETS : MAJOR_TARGETS;
}

function scoreShift(work, shift, priorityTargets) {
  const transposed = simplifyChordsInSheet(transposeSheet(work, shift));
  const chords = extractChords(transposed);
  const simplified = chords.map(simplifyChordName);
  const distinct = new Set(simplified);
  const score = [...distinct].filter((chord) => EASY_CHORDS.has(chord)).length;
  const firstSimple = simplified[0] ?? '';
  const landsOnPriority = priorityTargets.includes(firstSimple);
  return { shift, score, landsOnPriority, absShift: Math.abs(shift), sheet: transposed };
}

function pickBestShift(work, firstChord) {
  const priorityTargets = easyKeyTargets(firstChord);
  let best = null;
  let bestKey = null;

  for (let shift = 0; shift < 12; shift += 1) {
    const candidate = scoreShift(work, shift, priorityTargets);
    const sortKey = [candidate.score, candidate.landsOnPriority, -candidate.absShift];
    if (best == null || compareSortKeys(sortKey, bestKey) > 0) {
      best = candidate;
      bestKey = sortKey;
    }
  }

  return best;
}

function compareSortKeys(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return left[index] > right[index] ? 1 : -1;
    }
  }
  return 0;
}

function resultKeyLabel(resultSheet) {
  const chords = extractChords(resultSheet);
  if (chords.length === 0) return '';
  const firstSimple = simplifyChordName(chords[0]);
  return KNOWN_KEY_LABELS.has(firstSimple) ? firstSimple : firstSimple;
}

function evaluateCandidate(work, shift) {
  const transposed = simplifyChordsInSheet(transposeSheet(work, shift));
  const chords = extractChords(transposed).map(simplifyChordName);
  return isEasyProgression(chords) ? transposed : null;
}

function anyShiftFullyEasy(work, shifts) {
  return shifts.some((shift) => evaluateCandidate(work, shift) != null);
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

function formatSemitoneShift(semitones, isHe) {
  if (semitones === 0) return '';
  const abs = Math.abs(semitones);
  if (isHe) {
    const unit = abs === 1 ? 'חצי טון' : 'חצי טונים';
    const sign = semitones > 0 ? '+' : '−';
    return `${sign}${abs} ${unit}`;
  }
  const unit = abs === 1 ? 'semitone' : 'semitones';
  return semitones > 0 ? `+${semitones} ${unit}` : `${semitones} ${unit}`;
}

function suggestedCapoFret(easyVersion, transposeSemitones) {
  const easyShift = easyVersion.shift ?? 0;
  const totalShift = easyShift + transposeSemitones;

  if (easyVersion.capo != null) {
    return easyVersion.capo - transposeSemitones;
  }
  if (totalShift > 0) {
    return totalShift;
  }
  return null;
}

/** Build the easy-version banner text, including key shift and capo guidance. */
export function formatEasyDisplayNote(easyVersion, transposeSemitones = 0, language = 'en') {
  if (!easyVersion?.available) return '';

  const isHe = language === 'he';
  const base = isHe ? easyVersion.noteHe : easyVersion.noteEn;
  const easyShift = easyVersion.shift ?? 0;
  const totalShift = easyShift + transposeSemitones;
  const extras = [];

  if (totalShift !== 0) {
    extras.push(formatSemitoneShift(totalShift, isHe));
  }

  const capoFret = suggestedCapoFret(easyVersion, transposeSemitones);
  const capoAlreadyInBase = easyVersion.capo != null && transposeSemitones === 0;
  if (capoFret != null && capoFret > 0 && capoFret <= 11 && !capoAlreadyInBase) {
    extras.push(isHe ? `קאפו ${capoFret} מומלץ` : `Capo ${capoFret} suggested`);
  }

  if (extras.length === 0) return base;
  return `${base} · ${extras.join(' · ')}`;
}

/**
 * @returns {{
 *   text: string,
 *   noteHe: string,
 *   noteEn: string,
 *   key: string|null,
 *   capo: number|null,
 *   shift: number,
 *   available: boolean,
 * }}
 */
export function buildEasyVersion(text, language = 'en') {
  const empty = {
    text: '',
    noteHe: '',
    noteEn: '',
    key: null,
    capo: null,
    shift: 0,
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
      shift: 0,
      available: true,
    };
  }

  if (!anyShiftFullyEasy(work, [...Array(12).keys()])) {
    for (let capo = 1; capo < 12; capo += 1) {
      const candidate = evaluateCandidate(work, -capo);
      if (candidate) {
        return {
          text: candidate,
          noteHe: easyNoteHe(null, { capo }),
          noteEn: easyNoteEn(null, { capo }),
          key: null,
          capo,
          shift: -capo,
          available: true,
        };
      }
    }
  }

  const first = chords[0];
  const best = pickBestShift(work, first);
  const keyLabel = resultKeyLabel(best.sheet);

  return {
    text: best.sheet,
    noteHe: easyNoteHe(keyLabel),
    noteEn: easyNoteEn(keyLabel),
    key: keyLabel,
    capo: null,
    shift: best.shift,
    available: true,
  };
}
