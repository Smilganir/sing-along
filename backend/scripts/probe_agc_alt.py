import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

for path in [
    "/chords/index/gb/minor",
    "/chords/index/db/major",
    "/chords/index/cs/minor",
    "/chords/index/fs/minor",
    "/chords/index/bb/major",
    "/chords/index/eb/major",
    "/chords/index/ab/major",
    "/chords/index/f%23/minor",
    "/chords/index/c%23/major",
]:
    r = requests.get(BASE + path, headers=UA, timeout=15)
    img = re.search(r'src="(/chords/img/[^"]+)"', r.text)
    print(r.status_code, path, img.group(1) if img else "-")
