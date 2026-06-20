# Implementation spec — fix easy-version algorithm

> Hand-off spec for implementing the easy-version chord fixes. Self-contained:
> an executor should be able to implement everything below without prior chat
> context. Do **not** change unrelated behavior.

## Problem

Activating the "Easy version" toggle mis-simplifies chords:

- **Bug:** major-seventh chords become **minor**. `Cmaj7 → Cm`, `Fmaj7 → Fm`.
  Cause: `simplify_chord_name` checks `lowered.startswith("m")` before any
  major check, and `"maj7".startswith("m")` is `True`.
  Expected: `Cmaj7 → C`, `Fmaj7 → F` (simplify to the correct **major** triad).
- **Coverage gap:** the easy-version regex is narrower than the app's real chord
  detector, so chords like `Bm7b5` and `C6` are **silently dropped** from
  `extract_chords` — they are never simplified or transposed.
- **Key selection:** when no key makes the progression 100% easy, the algorithm
  bails to an arbitrary first target instead of the most convenient key.

## Confirmed decisions

1. **Simplifier approach:** use the canonical suffix vocabulary's `intervals`
   (`backend/services/chord_suffixes.py` / `frontend/src/constants/chordSuffixes.js`)
   to decide major vs minor. No string-prefix guessing.
2. **Smart key selection:** include best-effort key selection (Part C).
3. **Slash chords:** simplify the base, **keep the bass note**
   (`Cmaj7/E → C/E`).

## Files to change

| File | Change |
|---|---|
| `backend/services/chord_suffixes.py` | Add `CHORD_SUFFIX_PATTERN` + a triad-simplify helper (mirror of the JS exports) |
| `backend/services/easy_chords.py` | New simplifier, widened regex, smart key selection |
| `frontend/src/constants/chordSuffixes.js` | Add an `isMinorCanonical()` helper if convenient (exports already exist) |
| `frontend/src/utils/transpose.js` | Widen `CHORD_PATTERN` (built from `CHORD_SUFFIX_PATTERN` + optional `/bass`) |
| `frontend/src/utils/easyVersion.js` | Mirror new simplifier + smart key selection |
| `backend/tests/test_easy_chords.py` | Add cases (below) |
| `frontend/src/utils/easyVersion.test.js` *(new, optional)* | Vitest mirror of key cases |

> The narrow chord regex currently lives in **three** files — `easy_chords.py`,
> `easyVersion.js`, and `transpose.js`. All three must be widened together, or
> extraction/transposition stays broken. Backend and frontend logic must remain
> behaviorally equivalent.

## Part A — Correct simplification (canonical)

Rewrite `simplify_chord_name(chord)` / `simplifyChordName(chord)`:

1. If the chord contains `/`: split into `base` / `bass`; return
   `simplify(base) + "/" + bass` (keep the bass note).
2. Match `root` + `suffix`. No suffix → return `root`.
3. `canonical = SUFFIX_TO_CANONICAL[suffix]` (try exact, then lower-case).
4. If found, read `intervals = SUFFIX_BY_CANONICAL[canonical].intervals`:
   - **minor** (`root + "m"`) when `3 in intervals and 4 not in intervals`
   - **major** (`root`) otherwise
5. Unknown suffix → corrected heuristic, in this exact order:
   `startswith("maj")` or `== "M"` → major; `"dim" in s` → minor;
   `"aug" in s` → major; `startswith("m"/"min")` → minor; else major.

Result table (must hold):

| In | Out | | In | Out |
|---|---|---|---|---|
| `Cmaj7` | `C` | | `Cm7` | `Cm` |
| `Fmaj7` | `F` | | `Bm7b5` | `Bm` |
| `C6` / `G9` | `C` / `G` | | `Cdim` / `Cdim7` | `Cm` |
| `Dsus4` / `Cadd9` | `D` / `C` | | `Caug` | `C` |
| `Cmaj7/E` | `C/E` | | `Cmmaj7` | `Cm` |

## Part B — Widen the regex (close coverage gap)

In `chord_suffixes.py` add (mirroring `chordSuffixes.js`):

```python
CHORD_SUFFIX_PATTERN = "(?:" + "|".join(re.escape(a) for a in _aliases_longest_first) + ")?"
```

where `_aliases_longest_first` = all non-empty aliases except `"M"`, sorted by
length descending. Build the chord regex in **all three** modules as:

```
\b([A-G][#b]?<CHORD_SUFFIX_PATTERN>(?:/[A-G][#b]?)?)\b
```

After this, `extract_chords` must capture `Bm7b5`, `C6`, `9`, `sus`, `add`, and
slash chords (today it drops `Bm7b5` and `C6`).

## Part C — Convenient ladder (best-effort key selection)

Replace the all-or-nothing target loop in `apply_easy_versions` /
`buildEasyVersion`:

1. If the simplified progression is already all-easy → return unchanged
   (current behavior, keep it).
2. Otherwise, score **all 12 transpositions** of the simplified sheet:
   `score = count of distinct chords whose simplified form is in EASY_CHORDS`.
3. Pick the shift with the **max score**. Tie-break:
   1. first chord lands on a priority target (`Am, C, Em, G` per major/minor),
   2. then smallest `|shift|`.
4. Label the note by the resulting key (target label if it matches one of the
   known targets, else the first chord's simplified name).
5. Keep the capo branch as a refinement: if no transposition reaches *fully*
   easy but a capo (negative shift) does, prefer that with the existing capo
   note.

For 'צליל מכוון' (already in Am), the best score keeps shift 0 and yields:
`Am · Bm · Dm · F · C · G · E` — `Cmaj7→C`, `Fmaj7→F`, only the unavoidable
`Bm` remains non-open.

## Tests to add (`backend/tests/test_easy_chords.py`)

- `simplify_chord_name`: `Cmaj7→C`, `Fmaj7→F`, `C6→C`, `G9→G`, `Dsus4→D`,
  `Cm7→Cm`, `Bm7b5→Bm`, `Cdim→Cm`, `Caug→C`, `Cmaj7/E→C/E`.
- `extract_chords` of `"Am Bm7b5 Dm Fmaj7 Cmaj7 C6 G9 Dsus4 Cadd9"` includes
  **all** of them (especially `Bm7b5` and `C6`).
- End-to-end: an Am sheet containing `Cmaj7`/`Fmaj7` → easy output contains `C`
  and `F`, and contains **no** `Cm`/`Fm`.
- Key selection: a song in a hard key transposes to maximize easy chords.

Run: `python -m unittest discover -s tests` (backend),
`npm test` (frontend, if the Vitest mirror is added).

## Acceptance criteria

- No major-family chord is ever converted to minor.
- Every chord the display detects is also simplified/transposed by the easy
  engine.
- Easy version picks the key with the most open chords; 'צליל מכוון' stays in
  Am with `Cmaj7→C`, `Fmaj7→F`.
- Backend and frontend produce matching results; all tests green.
