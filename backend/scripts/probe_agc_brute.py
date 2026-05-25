import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

candidates = []
roots = ["a", "b", "c", "d", "e", "f", "g", "a-sharp", "c-sharp", "d-sharp", "f-sharp", "g-sharp", "b-flat", "e-flat", "a-flat", "d-flat", "g-flat"]
suffixes = ["major", "minor", "7", "maj7", "m7", "minor7", "sus4", "sus2", "dim", "aug", "add9", "6"]
for root in roots:
    for suf in suffixes:
        candidates.append(f"/chords/index/{root}/{suf}")

for path in candidates:
    r = requests.get(BASE + path, headers=UA, timeout=15)
    if r.status_code == 200 and "guitar-chord-" in r.text:
        import re
        img = re.search(r'src="(/chords/img/[^"]+)"', r.text)
        print(path, "->", img.group(1) if img else "?")
