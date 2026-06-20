import { describe, expect, it } from 'vitest';

import { simplifyChordToTriad } from '../constants/chordSuffixes.js';
import { buildEasyVersion, formatEasyDisplayNote, simplifyChordName } from './easyVersion.js';
import { extractChords } from './transpose.js';

describe('simplifyChordName', () => {
  it('maps major-family extensions to major triads and keeps slash bass', () => {
    const cases = {
      Cmaj7: 'C',
      Fmaj7: 'F',
      C6: 'C',
      G9: 'G',
      Dsus4: 'D',
      Cm7: 'Cm',
      Bm7b5: 'Bm',
      Cdim: 'Cm',
      Caug: 'C',
      'Cmaj7/E': 'C/E',
    };
    for (const [input, expected] of Object.entries(cases)) {
      expect(simplifyChordName(input)).toBe(expected);
      expect(simplifyChordToTriad(input)).toBe(expected);
    }
  });
});

describe('extractChords', () => {
  it('captures extended suffixes used by the easy engine', () => {
    const line = 'Am Bm7b5 Dm Fmaj7 Cmaj7 C6 G9 Dsus4 Cadd9';
    const chords = extractChords(line);
    for (const expected of ['Am', 'Bm7b5', 'Dm', 'Fmaj7', 'Cmaj7', 'C6', 'G9', 'Dsus4', 'Cadd9']) {
      expect(chords).toContain(expected);
    }
  });
});

describe('buildEasyVersion', () => {
  it('keeps an Am sheet in Am without turning maj7 chords minor', () => {
    const sample = 'Am Bm Dm Fmaj7 Cmaj7 C6 G9 Dsus4 Cadd9';
    const result = buildEasyVersion(sample, 'en');
    expect(result.available).toBe(true);
    expect(result.text).toContain('C');
    expect(result.text).toContain('F');
    expect(result.text).not.toContain('Cm');
    expect(result.text).not.toContain('Fm');
    expect(result.noteEn).toContain('Am');
    expect(result.shift).toBe(0);
  });
});

describe('formatEasyDisplayNote', () => {
  it('adds semitone shift and capo guidance when the key is moved', () => {
    const sample = 'B\nlyric\nE\nmore';
    const easy = buildEasyVersion(sample, 'en');
    expect(easy.shift).toBeGreaterThan(0);

    expect(formatEasyDisplayNote(easy, 0, 'en')).toContain(`+${easy.shift} semitone`);
    expect(formatEasyDisplayNote(easy, 0, 'en')).toContain(`Capo ${easy.shift} suggested`);
    expect(formatEasyDisplayNote(easy, 1, 'en')).toContain(`+${easy.shift + 1} semitones`);
    expect(formatEasyDisplayNote(easy, 1, 'en')).toContain(`Capo ${easy.shift + 1} suggested`);
  });

  it('updates capo guidance after manual key changes on a capo-based easy sheet', () => {
    const sample = 'F#  B  C#  D#m  E  A';
    const easy = buildEasyVersion(sample, 'en');
    if (easy.capo == null) return;

    expect(formatEasyDisplayNote(easy, 0, 'en')).toContain(`capo on fret ${easy.capo}`);
    expect(formatEasyDisplayNote(easy, 1, 'en')).toContain('+1 semitone');
    expect(formatEasyDisplayNote(easy, 1, 'en')).toContain(`Capo ${easy.capo - 1} suggested`);
  });

  it('leaves an unchanged Am sheet note unchanged', () => {
    const easy = buildEasyVersion('Am Bm Dm F C G E', 'en');
    expect(formatEasyDisplayNote(easy, 0, 'en')).toBe(easy.noteEn);
    expect(formatEasyDisplayNote(easy, 2, 'en')).toBe('Easy version — Am key · +2 semitones · Capo 2 suggested');
  });
});
