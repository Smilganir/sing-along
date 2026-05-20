import json
import re
import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def probe_echords(artist: str, title: str) -> None:
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    url = f"https://www.e-chords.com/chords/{slug(artist)}/{slug(title)}"
    r = requests.get(url, headers=headers, timeout=30)
    print("echords", url, r.status_code)
    if r.ok:
        pre = BeautifulSoup(r.text, "html.parser").find("pre")
        print(pre.get_text()[:200] if pre else "no pre")


def probe_nagnu(title: str) -> None:
    r = requests.get(
        "https://www.nagnu.co.il/",
        params={"go": "search", "search": title},
        headers=headers,
        timeout=30,
    )
    soup = BeautifulSoup(r.text, "html.parser")
    href = None
    for a in soup.select("a[href]"):
        candidate = a.get("href", "")
        if candidate.startswith("/%D7%90%D7%95%D7%9E%D7%A0%D7%99%D7%9D/") and candidate.endswith(
            "%D7%90%D7%A7%D7%95%D7%A8%D7%93%D7%99%D7%9D"
        ):
            href = candidate
            print("nagnu hit", a.get_text(strip=True)[:50], href)
            break
    if not href:
        return
    page = requests.get("https://www.nagnu.co.il" + href, headers=headers, timeout=30)
    print("page", page.status_code)
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page.text, re.S)
    if match:
        data = json.loads(match.group(1))
        props = data.get("props", {}).get("pageProps", {})
        print("pageProps keys", props.keys())
        song = props.get("song") or props.get("data") or props
        print(str(song)[:600])
    else:
        print("no next data")


if __name__ == "__main__":
    probe_echords("OneRepublic", "Counting Stars")
    probe_echords("Eminem", "Lose Yourself")
    probe_nagnu("קחי לך זמן")
