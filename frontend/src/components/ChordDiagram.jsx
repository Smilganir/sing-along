import './ChordDiagram.css';
import { FINGER_COLORS, STRING_STATUS_COLOR } from '../constants/fingerColors.js';

const STRING_COUNT = 6;
const FRET_COUNT = 4;
const SVG_WIDTH = 120;          // × size=1.5 → 180 px, same as AGC display width
const PADDING_TOP = 20;
const PADDING_LEFT = 32;        // 32 × 1.5 = 48 px — enough margin for labels
const PADDING_SIDE = 6;
const FRETBOARD_WIDTH = SVG_WIDTH - PADDING_LEFT - PADDING_SIDE; // 82
const FRETBOARD_HEIGHT = 84;    // 4 rows × 21 SVG u → 31.5 px per row at 1.5×
const SVG_HEIGHT_BASE = PADDING_TOP + FRETBOARD_HEIGHT + 24;     // 128 → 192 px at 1.5×
const NOTES_EXTRA = 20; // extra height when showNotes=true
const STRING_SPACING = FRETBOARD_WIDTH / (STRING_COUNT - 1);
const FRET_SPACING = FRETBOARD_HEIGHT / FRET_COUNT;
const DOT_RADIUS = 7;
const FINGER_DOT_STROKE = 'white';
const FINGER_DOT_STROKE_WIDTH = 1;

const CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const OPEN_INDICES = [4, 9, 2, 7, 11, 4];
const STRING_NAMES = ['E', 'A', 'D', 'G', 'B', 'E'];

function getNoteAtFret(stringIndex, fret) {
  if (fret < 0) return null;
  return CHROMATIC[(OPEN_INDICES[stringIndex] + fret) % 12];
}

export default function ChordDiagram({ chord, size = 1, coloredFingers = true, showNotes = false }) {
  const { name, frets, fingers, baseFret = 1, barres } = chord;

  const svgHeight = showNotes ? SVG_HEIGHT_BASE + NOTES_EXTRA : SVG_HEIGHT_BASE;

  const getDotFill = (fingerNum) =>
    coloredFingers && fingerNum >= 1 && fingerNum <= 4
      ? FINGER_COLORS[fingerNum]
      : 'var(--chord-diagram-dot, #60a5fa)';

  const getX = (stringIndex) => PADDING_LEFT + stringIndex * STRING_SPACING;
  const getY = (fretIndex) => PADDING_TOP + fretIndex * FRET_SPACING;

  const bottomY = getY(FRET_COUNT);
  const stringNamesY = bottomY + 15;
  const notesY = bottomY + 30;

  return (
    <div className="chord-diagram">
      <svg
        width={SVG_WIDTH * size}
        height={svgHeight * size}
        viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <text
          x={SVG_WIDTH / 2}
          y={12}
          textAnchor="middle"
          className="chord-name-label"
          fontSize="13"
          fontWeight="700"
        >
          {name}
        </text>

        {/* Nut bar — only when chord starts at first fret */}
        {baseFret === 1 && (
          <line
            x1={PADDING_LEFT}
            y1={PADDING_TOP}
            x2={SVG_WIDTH - PADDING_SIDE}
            y2={PADDING_TOP}
            stroke="var(--chord-diagram-text, #e2e8f0)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        )}

        {/* Fret row labels — centred in the left margin, fully visible */}
        {Array.from({ length: FRET_COUNT }).map((_, row) => (
          <text
            key={`fr-${row}`}
            x={PADDING_LEFT / 2}
            y={getY(row + 1) - FRET_SPACING / 2}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="var(--chord-diagram-text, #e2e8f0)"
          >
            {baseFret + row}
          </text>
        ))}

        {/* Fret lines */}
        {Array.from({ length: FRET_COUNT + 1 }).map((_, i) => (
          <line
            key={`fret-${i}`}
            x1={PADDING_LEFT}
            y1={getY(i)}
            x2={SVG_WIDTH - PADDING_SIDE}
            y2={getY(i)}
            stroke="var(--chord-diagram-fret, #334155)"
            strokeWidth={i === 0 && baseFret === 1 ? 0 : 1.5}
          />
        ))}

        {/* String lines */}
        {Array.from({ length: STRING_COUNT }).map((_, i) => {
          const thicknessIndex = STRING_COUNT - 1 - i;
          return (
            <line
              key={`string-${i}`}
              x1={getX(i)}
              y1={PADDING_TOP}
              x2={getX(i)}
              y2={bottomY}
              stroke="var(--chord-diagram-string, #94a3b8)"
              strokeWidth={1 + thicknessIndex * 0.2}
            />
          );
        })}

        {/* Barre bars */}
        {barres?.map((barre, idx) => {
          const displayFret = barre.fret - (baseFret - 1);
          const fromX = getX(STRING_COUNT - barre.fromString);
          const toX = getX(STRING_COUNT - barre.toString);
          const y = getY(displayFret) - FRET_SPACING / 2;
          return (
            <rect
              key={`barre-${idx}`}
              x={Math.min(fromX, toX) - DOT_RADIUS}
              y={y - DOT_RADIUS}
              width={Math.abs(toX - fromX) + DOT_RADIUS * 2}
              height={DOT_RADIUS * 2}
              rx={DOT_RADIUS}
              fill={getDotFill(1)}
              stroke={FINGER_DOT_STROKE}
              strokeWidth={FINGER_DOT_STROKE_WIDTH}
            />
          );
        })}

        {/* Fret dots — muted, open, fingered */}
        {frets.map((fret, i) => {
          const x = getX(i);
          if (fret === -1) {
            return (
              <text
                key={`m-${i}`}
                x={x}
                y={PADDING_TOP - 8}
                textAnchor="middle"
                fontSize="12"
                fill={STRING_STATUS_COLOR}
                fontWeight="500"
              >
                X
              </text>
            );
          }
          if (fret === 0) {
            return (
              <circle
                key={`o-${i}`}
                cx={x}
                cy={PADDING_TOP - 11}
                r={5}
                fill={STRING_STATUS_COLOR}
              />
            );
          }
          const displayFret = fret - (baseFret - 1);
          // Skip dots that fall outside the visible fret window
          if (displayFret < 1 || displayFret > FRET_COUNT) return null;
          const y = getY(displayFret) - FRET_SPACING / 2;
          const hasBarre = barres?.some(
            (b) => b.fret === fret && i >= STRING_COUNT - b.fromString && i <= STRING_COUNT - b.toString,
          );
          if (hasBarre) return null;

          const fingerNum = fingers[i];
          const dotFill = getDotFill(fingerNum);
          return (
            <g key={`f-${i}`}>
              <circle
                cx={x}
                cy={y}
                r={DOT_RADIUS}
                fill={dotFill}
                stroke={FINGER_DOT_STROKE}
                strokeWidth={FINGER_DOT_STROKE_WIDTH}
              />
              {fingerNum > 0 && (
                <text
                  x={x}
                  y={y + 4}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#0f172a"
                  fontWeight="700"
                >
                  {fingerNum}
                </text>
              )}
            </g>
          );
        })}

        {/* String name labels (E A D G B E) */}
        {STRING_NAMES.map((name, i) => (
          <text
            key={`sn-${i}`}
            x={getX(i)}
            y={stringNamesY}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="var(--chord-diagram-text, #e2e8f0)"
            opacity="0.7"
          >
            {name}
          </text>
        ))}

        {/* Chord note names (optional) */}
        {showNotes && (
          <g className="chord-diagram__notes-row">
            <line
              x1={PADDING_LEFT}
              y1={bottomY + 21}
              x2={SVG_WIDTH - PADDING_SIDE}
              y2={bottomY + 21}
              stroke="var(--chord-diagram-fret, #334155)"
              strokeWidth="0.8"
              strokeDasharray="2,2"
            />
            {frets.map((fret, i) => {
              const note =
                fret === -1
                  ? '×'
                  : chord.notes && chord.notes.length === 6
                    ? chord.notes[i]
                    : getNoteAtFret(i, fret);
              const x = getX(i);
              return (
                <text
                  key={`note-${i}`}
                  x={x}
                  y={notesY}
                  textAnchor="middle"
                  fontSize="8"
                  fontWeight={fret === -1 ? '400' : '700'}
                  fill={fret === -1 ? 'var(--chord-diagram-muted, #94a3b8)' : 'var(--chord-diagram-accent, #93c5fd)'}
                  fontFamily="Heebo, sans-serif"
                >
                  {note}
                </text>
              );
            })}
          </g>
        )}
      </svg>
    </div>
  );
}
