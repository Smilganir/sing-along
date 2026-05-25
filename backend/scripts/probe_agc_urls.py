import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"


def probe(path: str) -> None:
    r = requests.head(BASE + path, headers=UA, timeout=15, allow_redirects=True)
    print(r.status_code, path)


for p in [
    "/chords/img/guitar-chord-c-major-1.svg",
    "/chords/img/guitar-chord-am-minor-1.svg",
    "/chords/img/guitar-chord-a-minor-1.svg",
    "/chords/img/guitar-chord-f-sharp-minor-1.svg",
    "/chords/img/guitar-chord-bb-major-1.svg",
    "/chords/img/guitar-chord-a-minor7-1.svg",
    "/chords/img/guitar-chord-g-major-7-1.svg",
]:
    probe(p)

for page in ["/chords/index/a/minor", "/chords/index/am/minor", "/chords/index/g/major7"]:
    r = requests.get(BASE + page, headers=UA, timeout=20)
    print("page", page, r.status_code)
    imgs = re.findall(r'src="(/chords/img/[^"]+)"', r.text)
    for img in imgs[:3]:
        print(" ", img)
