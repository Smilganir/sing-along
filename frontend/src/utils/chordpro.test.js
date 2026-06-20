import { describe, expect, it } from 'vitest';

import { isChordOnlyLine, parseChordPro, tokenizeChordLine } from './chordpro.js';

describe('power-chord detection', () => {
  it('recognizes common rock power-chord symbols', () => {
    for (const chord of ['A5', 'B5', 'C5', 'D5', 'E5', 'G5', 'Bb5', 'F#5']) {
      expect(isChordOnlyLine(chord)).toBe(true);
      expect(tokenizeChordLine(chord)).toEqual([
        { type: 'chord', text: chord, chord },
      ]);
    }
  });

  it('groups consecutive power-chord lines above the next lyric', () => {
    const blocks = parseChordPro('A5\nB5\nC5\nD5\nOhh! Sweet child');
    expect(blocks).toHaveLength(1);
    expect(blocks[0].chords).toBe('A5   B5   C5   D5');
    expect(blocks[0].lyrics).toBe('Ohh! Sweet child');
  });

  it('skips solo markers instead of rendering them as lyrics', () => {
    const blocks = parseChordPro('A5\nB5\nOhh! Sweet child\nSolo\nC5\nD5\nWhere do we go');
    expect(blocks.some((b) => b.lyrics === 'Solo')).toBe(false);
    expect(blocks.find((b) => b.lyrics === 'Where do we go')?.chords).toBe('C5   D5');
  });
});
