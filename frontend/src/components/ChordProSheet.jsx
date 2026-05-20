import { parseChordPro } from '../utils/chordpro.js';

export default function ChordProSheet({ text, language, lyricsOnly }) {
  const blocks = parseChordPro(text, { lyricsOnly });
  const isHebrew = language === 'he';

  if (blocks.length === 0) {
    return <p className="sing-sheet-empty">No lyrics available for this song.</p>;
  }

  return (
    <div className={`sing-sheet ${isHebrew ? 'sing-sheet--he' : 'sing-sheet--en'}`}>
      {blocks.map((block, index) => (
        <div key={index} className="sing-verse-block">
          {block.chords && (
            <pre
              className="sing-sheet-chords"
              dir={isHebrew ? 'rtl' : 'ltr'}
              aria-hidden={lyricsOnly}
            >
              {block.chords}
            </pre>
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
