import ChordToken from './ChordToken.jsx';
import { lyricAnchorHash, parseChordPro, tokenizeChordLine } from '../utils/chordpro.js';
import { isNeginaSheet } from '../utils/chordSources.js';

function ChordLine({ line, useNeginaHebrewLayout }) {
  if (useNeginaHebrewLayout) {
    return (
      <pre className="sing-sheet-chords sing-sheet-chords--negina-he" dir="rtl">
        {line}
      </pre>
    );
  }

  const tokens = tokenizeChordLine(line);

  return (
    <pre className="sing-sheet-chords">
      {tokens.map((token, index) => {
        if (token.type === 'space') {
          return <span key={index}>{token.text}</span>;
        }
        if (token.type === 'chord') {
          return (
            <span key={index}>
              <ChordToken chord={token.chord}>
                {token.text}
              </ChordToken>
            </span>
          );
        }
        return <span key={index}>{token.text}</span>;
      })}
    </pre>
  );
}

export default function ChordProSheet({ text, language, lyricsOnly, chordSource, sourceUrl }) {
  const isHebrew = language === 'he';
  const useNeginaHebrewLayout = isHebrew && isNeginaSheet(chordSource, sourceUrl);
  const blocks = parseChordPro(text, { lyricsOnly, neginaLayout: useNeginaHebrewLayout });

  if (blocks.length === 0) {
    return <p className="sing-sheet-empty">No lyrics available for this song.</p>;
  }

  const sheetClass = [
    'sing-sheet',
    isHebrew ? 'sing-sheet--he' : 'sing-sheet--en',
    useNeginaHebrewLayout ? 'sing-sheet--negina-he' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={sheetClass}>
      {blocks.map((block, index) => (
        <div
          key={index}
          className="sing-verse-block"
          data-anchor={lyricAnchorHash(block.lyrics)}
        >
          {block.chords && !lyricsOnly && (
            <ChordLine line={block.chords} useNeginaHebrewLayout={useNeginaHebrewLayout} />
          )}
          {block.lyrics && (
            <pre className="sing-sheet-lyrics" dir={isHebrew ? 'rtl' : 'ltr'}>
              {block.lyrics}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
