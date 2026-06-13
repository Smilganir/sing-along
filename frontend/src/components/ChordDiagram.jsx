import './ChordDiagram.css';
import { FINGER_COLORS } from '../constants/fingerColors.js';

const STRING_COUNT = 6;
const FRET_COUNT = 5;
const SVG_WIDTH = 120;
const PADDING_TOP = 36;
const PADDING_SIDE = 20;
const FRETBOARD_WIDTH = SVG_WIDTH - PADDING_SIDE * 2;
const NOTES_EXTRA = 30;
const SVG_HEIGHT_BASE = 160;
const FRETBOARD_HEIGHT = SVG_HEIGHT_BASE - PADDING_TOP - 16;
const STRING_SPACING = FRETBOARD_WIDTH / (STRING_COUNT - 1);
const FRET_SPACING = FRETBOARD_HEIGHT / FRET_COUNT;
const DOT_RADIUS = 7;

const CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const OPEN_INDICES = [4, 9, 2, 7, 11, 4];

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
      : 'var(--chord-diagram-dot)';

  const getX = (stringIndex) => PADDING_SIDE + stringIndex * STRING_SPACING;
  const getY = (fretIndex) => PADDING_TOP + fretIndex * FRET_SPACING;

  const bottomY = getY(FRET_COUNT);
  const notesY = bottomY + 13;

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
          y={14}
          textAnchor="middle"
          className="chord-name-label"
          fontSize="16"
          fontWeight="700"
        >
          {name}
        </text>

        {baseFret === 1 ? (
          <line
            x1={PADDING_SIDE}
            y1={PADDING_TOP}
            x2={SVG_WIDTH - PADDING_SIDE}
            y2={PADDING_TOP}
            stroke="var(--chord-diagram-text)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        ) : (
          <text
            x={PADDING_SIDE - 14}
            y={PADDING_TOP + FRET_SPACING / 2 + 5}
            textAnchor="middle"
            fontSize="12"
            fill="var(--chord-diagram-text)"
            fontWeight="800"
          >
            {baseFret}
          </text>
        )}

        {Array.from({ length: FRET_COUNT + 1 }).map((_, i) => (
          <line
            key={`fret-${i}`}
            x1={PADDING_SIDE}
            y1={getY(i)}
            x2={SVG_WIDTH - PADDING_SIDE}
            y2={getY(i)}
            stroke="var(--chord-diagram-fret)"
            strokeWidth={i === 0 && baseFret === 1 ? 0 : 1.5}
          />
        ))}

        {Array.from({ length: STRING_COUNT }).map((_, i) => {
          const thicknessIndex = STRING_COUNT - 1 - i;
          return (
            <line
              key={`string-${i}`}
              x1={getX(i)}
              y1={PADDING_TOP}
              x2={getX(i)}
              y2={bottomY}
              stroke="var(--chord-diagram-string)"
              strokeWidth={1 + thicknessIndex * 0.2}
            />
          );
        })}

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
            />
          );
        })}

        {frets.map((fret, i) => {
          const x = getX(i);
          if (fret === -1) {
            return (
              <text
                key={`m-${i}`}
                x={x}
                y={PADDING_TOP - 8}
                textAnchor="middle"
                fontSize="14"
                fill="var(--chord-diagram-muted)"
                fontWeight="600"
              >
                ✕
              </text>
            );
          }
          if (fret === 0) {
            return (
              <circle
                key={`o-${i}`}
                cx={x}
                cy={PADDING_TOP - 12}
                r={5}
                fill="none"
                stroke="var(--chord-diagram-open)"
                strokeWidth="1.5"
              />
            );
          }
          const displayFret = fret - (baseFret - 1);
          const y = getY(displayFret) - FRET_SPACING / 2;
          const hasBarre = barres?.some(
            (b) => b.fret === fret && i >= STRING_COUNT - b.fromString && i <= STRING_COUNT - b.toString,
          );
          if (hasBarre) return null;

          const fingerNum = fingers[i];
          const dotFill = getDotFill(fingerNum);
          return (
            <g key={`f-${i}`}>
              <circle cx={x} cy={y} r={DOT_RADIUS} fill={dotFill} />
              {fingerNum > 0 && (
                <text
                  x={x}
                  y={y + 4}
                  textAnchor="middle"
                  fontSize="9"
                  fill="white"
                  fontWeight="600"
                >
                  {fingerNum}
                </text>
              )}
            </g>
          );
        })}

        {showNotes && (
          <g className="chord-diagram__notes-row">
            <line
              x1={PADDING_SIDE}
              y1={bottomY + 4}
              x2={SVG_WIDTH - PADDING_SIDE}
              y2={bottomY + 4}
              stroke="var(--chord-diagram-fret)"
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
                  fill={fret === -1 ? 'var(--chord-diagram-muted)' : 'var(--chord-diagram-accent)'}
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
