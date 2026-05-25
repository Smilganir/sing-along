import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

for path in [
    "/chords/index/b%flat/major",
    "/chords/index/b%flat/minor",
    "/chords/index/e%flat/major",
    "/chords/index/a%flat/major",
    "/chords/index/d%flat/major",
    "/chords/index/g%flat/major",
    "/chords/index/b%23/major",
    "/chords/index/a%23/minor",
    "/chords/index/d%23/major",
    "/chords/index/g%23/minor",
    "/chords/index/e%23/major",
]:
    r = requests.get(BASE + path, headers=UA, timeout=15)
    img = re.search(r'src="(/chords/img/[^"]+)"', r.text)
    print(r.status_code, path, img.group(1) if img else "-")
