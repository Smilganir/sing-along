/** True when sheet content came from negina.co.il (aligned LTR chord rows over RTL lyrics). */
export function isNeginaSheet(chordSource, sourceUrl) {
  if (chordSource === 'negina') {
    return true;
  }
  if (sourceUrl && /negina\.co\.il/i.test(sourceUrl)) {
    return true;
  }
  return false;
}
