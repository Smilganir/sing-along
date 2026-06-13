/** True for negina.co.il sheets (space-aligned chord rows over RTL lyrics). */
export function isNeginaSheet(chordSource, sourceUrl) {
  if (chordSource === 'negina') {
    return true;
  }
  if (sourceUrl && /negina\.co\.il/i.test(sourceUrl)) {
    return true;
  }
  return false;
}
