import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { adaptAgcSvgForDarkBg } from './chordDiagram.js';

const read = (name) =>
  readFileSync(fileURLToPath(new URL(`./__fixtures__/${name}`, import.meta.url)), 'utf-8');

describe('AGC SVG styler', () => {
  it('produces the golden dark-background output (must match the Python styler)', () => {
    const input = read('agc-sample.svg');
    const golden = read('agc-sample.golden.svg');
    expect(adaptAgcSvgForDarkBg(input)).toBe(golden);
  });
});
