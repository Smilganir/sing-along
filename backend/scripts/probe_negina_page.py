import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

url = "https://negina.co.il/chords/%D7%98%D7%95%D7%A0%D7%94/%D7%A2%D7%95%D7%9C%D7%9D-%D7%9E%D7%A9%D7%95%D7%92%D7%A2"
r = requests.get(url, headers=UA, timeout=30)
print("status", r.status_code)
soup = BeautifulSoup(r.text, "html.parser")
for el in soup.select("[class*='chord']"):
    cls = " ".join(el.get("class", []))
    txt = el.get_text("\n").strip()
    if txt and len(txt) < 200:
        print("el", cls, repr(txt[:80]))

# look for song body
for el in soup.find_all(["div", "section"], class_=True):
    cls = " ".join(el.get("class", []))
    if "song" in cls.lower() or "chord" in cls.lower():
        t = el.get_text("\n")
        if "Am" in t or "Cm" in t or "פזמון" in t:
            print("block", cls, t[:600])
            break

print("--- scripts ---")
for s in soup.find_all("script"):
    t = s.string or ""
    if "chords" in t.lower() and "artist" in t.lower() and len(t) < 30000:
        print(t[:800])
