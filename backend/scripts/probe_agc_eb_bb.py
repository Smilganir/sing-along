import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

for path in [
    "/chords/index/d%23/major",
    "/chords/index/e%23/major",
    "/chords/index/b%23/major",
    "/chords/index/a%23/major",
]:
    r = requests.get(BASE + path, headers=UA, timeout=15)
    import re as re2
    img = re2.search(r'src="(/chords/img/[^"]+)"', r.text)
    print(r.status_code, path, img.group(1) if img else "-")
