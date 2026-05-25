import ChordToken from './ChordToken.jsx';
import { lyricAnchorHash, parseChordPro, tokenizeChordLine } from '../utils/chordpro.js';

function ChordLine({ line, isHebrew }) {
  const tokens = tokenizeChordLine(line);

  return (
    <pre
      className="sing-sheet-chords"
      dir={isHebrew ? 'rtl' : 'ltr'}
    >
      {tokens.map((token, index) => {
        if (token.type === 'space') {
          return <span key={index}>{token.text}</span>;
        }
        if (token.type === 'chord') {
          return (
            <ChordToken key={index} chord={token.chord}>
              {token.text}
            </ChordToken>
          );
        }
        return <span key={index}>{token.text}</span>;
      })}
    </pre>
  );
}

export default function ChordProSheet({ text, language, lyricsOnly }) {
  const blocks = parseChordPro(text, { lyricsOnly });
  const isHebrew = language === 'he';

  if (blocks.length === 0) {
    return <p className="sing-sheet-empty">No lyrics available for this song.</p>;
  }

  return (
    <div className={`sing-sheet ${isHebrew ? 'sing-sheet--he' : 'sing-sheet--en'}`}>
      {blocks.map((block, index) => (
        <div
          key={index}
          className="sing-verse-block"
          data-anchor={lyricAnchorHash(block.lyrics)}
        >
          {block.chords && !lyricsOnly && (
            <ChordLine line={block.chords} isHebrew={isHebrew} />
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
