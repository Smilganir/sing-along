import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

roots = ["a-sharp", "c-sharp", "d-sharp", "f-sharp", "g-sharp", "b-flat", "e-flat", "a-flat", "d-flat", "g-flat"]
for root in roots:
    path = f"/chords/index/{root}/major"
    r = requests.get(BASE + path, headers=UA, timeout=15)
    img = re.search(r'src="(/chords/img/[^"]+)"', r.text) if r.status_code == 200 else None
    print(r.status_code, path, img.group(1) if img else "")

# verify Am mapping: Am -> a/minor
for chord, path in [("Am", "/chords/index/a/minor"), ("F#m", "/chords/index/f-sharp/minor"), ("Bb", "/chords/index/b-flat/major"), ("C#", "/chords/index/c-sharp/major")]:
    r = requests.head(BASE + f"/chords/img/guitar-chord-{path.split('/')[-2]}-{path.split('/')[-1]}-1.svg".replace("a-sharp","a-sharp"), timeout=15)
