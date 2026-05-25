import guitar from '@tombatossals/chords-db/lib/guitar.json';

const FLAT_TO_SHARP = {
  Db: 'C#',
  Eb: 'D#',
  Gb: 'F#',
  Ab: 'G#',
  Bb: 'A#',
};

const SUFFIX_TO_DB = {
  '': 'major',
  maj: 'major',
  m: 'minor',
  min: 'minor',
  '7': '7',
  maj7: 'maj7',
  M7: 'maj7',
  m7: 'minor7',
  min7: 'minor7',
  sus4: 'sus4',
  sus2: 'sus2',
  sus: 'sus4',
  dim: 'dim',
  aug: 'aug',
  add9: 'add9',
  '6': '6',
};

function normalizeRoot(root) {
  const letter = root[0].toUpperCase();
  const acc = root.slice(1);
  if (acc === 'b' || acc === '♭') return FLAT_TO_SHARP[`${letter}b`] ?? `${letter}b`;
  if (acc === '#' || acc === '♯') return `${letter}#`;
  return letter;
}

function mapSuffix(raw) {
  if (!raw) return 'major';
  const key = raw.trim();
  if (SUFFIX_TO_DB[key] != null) return SUFFIX_TO_DB[key];
  const lower = key.toLowerCase();
  if (SUFFIX_TO_DB[lower] != null) return SUFFIX_TO_DB[lower];
  if (lower === 'major') return 'major';
  if (lower === 'minor') return 'minor';
  if (lower === 'min7' || lower === 'minor7') return 'minor7';
  return null;
}

function parseChordName(chordName) {
  const clean = (chordName || '').trim().split('/')[0].trim();
  const match = clean.match(/^([A-G][#b]?)(.*)$/i);
  if (!match) return null;
  const key = normalizeRoot(match[1]);
  const suffix = mapSuffix(match[2]);
  if (!suffix) return null;
  return { key, suffix };
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

export function getChordsDbShape(chordName) {
  const parsed = parseChordName(chordName);
  if (!parsed) return null;

  const entries = guitar.chords[parsed.key];
  if (!entries) return null;

  const entry = entries.find((item) => item.suffix === parsed.suffix);
  if (!entry?.positions?.length) return null;

  return positionToShape(chordName, entry.positions[0]);
}

export function chordDiagramApiUrl(chordName) {
  return `/api/chords/diagram?chord=${encodeURIComponent(chordName)}&v=4`;
}

const FRET_LABEL_Y = { 61: 56, 101: 96, 141: 136, 181: 176 };
const AXIS_LABEL_FILL = '#e2e8f0';
const FINGER_DOT_ORANGE = '#9381CB';
const FINGER_DOT_YELLOW = '#97CBE8';

const FINGER_NUMBER_TEXT_RE =
  /<text x='(\d+)' y='(\d+)' font-size='14' font-family='Arial' fill='black'>(\d)<\/text>/g;

function isFretAxisLabel(tag) {
  return /\bx=(['"])20\1/.test(tag);
}

function isStringAxisLabel(tag) {
  return /\by=(['"])221\1/.test(tag);
}

/** Style all-guitar-chords SVGs for the dark popover (also applied server-side). */
export function adaptAgcSvgForDarkBg(svg) {
  let out = svg
    .replace(/fill='#e1dce2'/g, "fill='#243047'")
    .replace(/fill='#FF8000'/g, `fill='${FINGER_DOT_ORANGE}'`)
    .replace(/fill='#FFBB00'/g, `fill='${FINGER_DOT_YELLOW}'`)
    .replace(/stroke='black'/g, "stroke='#94a3b8'")
    .replace(
      /<svg\s+width=['"]230['"]\s+height=['"]230['"]/,
      "<svg width='230' height='250' viewBox='0 0 230 250' overflow='visible'",
    );

  out = out.replace(FINGER_NUMBER_TEXT_RE, (_match, x, y, digit) => {
    const cx = Number(x) + 4;
    const cy = Number(y) - 5;
    return `<text x='${cx}' y='${cy}' font-size='14' font-family='Arial' fill='black' text-anchor='middle' dominant-baseline='middle'>${digit}</text>`;
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
