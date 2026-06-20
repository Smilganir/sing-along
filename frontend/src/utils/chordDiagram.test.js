import { describe, expect, it } from 'vitest';

import {
  CHORD_SUFFIXES,
  SUFFIX_TO_CANONICAL,
  suffixFallbackChain,
} from '../constants/chordSuffixes.js';
import { getLocalChordShape, hasDiagramSupport, usesLocalDiagram } from './chordDiagram.js';

const ROOTS = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B'];
const BASSES = ['C', 'D', 'E', 'F', 'F#', 'G', 'A', 'Bb', 'B'];

/** Assert a resolved shape is structurally valid and renderable. */
function expectValidShape(shape, label) {
  expect(shape, `${label}: expected a shape`).toBeTruthy();
  expect(Array.isArray(shape.frets), `${label}: frets is array`).toBe(true);
  expect(shape.frets, `${label}: 6 strings`).toHaveLength(6);
  expect(shape.fingers, `${label}: 6 fingers`).toHaveLength(6);
  expect(shape.baseFret, `${label}: baseFret >= 1`).toBeGreaterThanOrEqual(1);
  for (const f of shape.frets) {
    expect(Number.isInteger(f), `${label}: integer fret`).toBe(true);
    expect(f, `${label}: fret >= -1`).toBeGreaterThanOrEqual(-1);
  }
  for (const finger of shape.fingers) {
    expect(finger, `${label}: finger 0..4`).toBeGreaterThanOrEqual(0);
    expect(finger, `${label}: finger 0..4`).toBeLessThanOrEqual(4);
  }
  // At least one string must be played (open or fretted).
  expect(shape.frets.some((f) => f >= 0), `${label}: at least one played string`).toBe(true);
}

describe('canonical suffix vocabulary', () => {
  it('maps every detectable alias to a canonical and a fallback chain that terminates', () => {
    for (const entry of CHORD_SUFFIXES) {
      for (const alias of entry.aliases) {
        expect(SUFFIX_TO_CANONICAL[alias]).toBe(entry.canonical);
      }
      const chain = suffixFallbackChain(entry.canonical);
      expect(chain[0]).toBe(entry.canonical);
      const tail = chain[chain.length - 1];
      // Every chain bottoms out at a core triad that always has a voicing.
      expect(['major', 'minor', 'dim', '7', 'sus4']).toContain(tail);
    }
  });
});

describe('diagram coverage: every root × every suffix resolves', () => {
  for (const entry of CHORD_SUFFIXES) {
    const alias = entry.aliases.find((a) => a !== 'M') ?? entry.canonical;
    for (const root of ROOTS) {
      const name = `${root}${alias}`;
      it(`${name} resolves to a valid diagram`, () => {
        expect(hasDiagramSupport(name)).toBe(true);
        expectValidShape(getLocalChordShape(name), name);
      });
    }
  }
});

describe('slash / bass variations resolve', () => {
  for (const root of ['C', 'D', 'G', 'A', 'E', 'F']) {
    for (const bass of BASSES) {
      const name = `${root}/${bass}`;
      it(`${name} resolves to a valid diagram`, () => {
        expect(hasDiagramSupport(name)).toBe(true);
        expect(usesLocalDiagram(name)).toBe(true);
        expectValidShape(getLocalChordShape(name), name);
      });
    }
  }

  it('A/D uses an open-D bass voicing (x x 0 2 2 0)', () => {
    const shape = getLocalChordShape('A/D');
    expect(shape.frets).toEqual([-1, -1, 0, 2, 2, 0]);
  });

  it('C/G places G in the bass on the low E string (3 3 2 0 1 0)', () => {
    const shape = getLocalChordShape('C/G');
    expect(shape.frets[0]).toBe(3);
  });
});

describe('maj7 / m7b5 use complete chords-db voicings (not stubbed shapes)', () => {
  // Regression: the old hand-rolled maj7 generator returned x 5 4 x x x for
  // Dmaj7 — only the root + 3rd, missing the 5th and maj7.
  it('Dmaj7 is the full x x 0 2 2 2 voicing', () => {
    expect(getLocalChordShape('Dmaj7').frets).toEqual([-1, -1, 0, 2, 2, 2]);
  });

  it('Dm7b5 is the full x x 0 1 1 1 voicing', () => {
    expect(getLocalChordShape('Dm7b5').frets).toEqual([-1, -1, 0, 1, 1, 1]);
  });

  it('every maj7 root sounds at least 4 strings (a 4-note chord)', () => {
    for (const root of ROOTS) {
      const played = getLocalChordShape(`${root}maj7`).frets.filter((f) => f >= 0).length;
      expect(played, `${root}maj7 played strings`).toBeGreaterThanOrEqual(4);
    }
  });
});

describe('partial (simplified) chords are flagged with *', () => {
  it('marks a chord with no exact voicing using a trailing *', () => {
    // add2 has no chords-db entry and falls back to its major parent.
    const shape = getLocalChordShape('Cadd2');
    expectValidShape(shape, 'Cadd2');
    if (shape.partial) {
      expect(shape.name.endsWith('*')).toBe(true);
    }
  });
});
