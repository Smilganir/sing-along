import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"


def page_imgs(path: str) -> None:
    r = requests.get(BASE + path, headers=UA, timeout=20)
    imgs = re.findall(r'src="(/chords/img/[^"]+)"', r.text)
    print(r.status_code, path, imgs[:1] if imgs else "no imgs")


for path in [
    "/chords/index/f/sharp-minor",
    "/chords/index/f-sharp/minor",
    "/chords/index/fs/minor",
    "/chords/index/b/flat-major",
    "/chords/index/bb/major",
    "/chords/index/a/minor7",
    "/chords/index/a/minor-7",
    "/chords/index/g/7",
    "/chords/index/g/seventh",
    "/chords/index/g/major-7",
    "/chords/index/c/sus4",
    "/chords/index/d/minor7",
    "/chords/index/e/minor7",
    "/chords/index/f/major",
    "/chords/index/c/sharp-minor",
    "/chords/index/c-sharp/minor",
]:
    page_imgs(path)
