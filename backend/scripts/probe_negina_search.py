import re
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

query = "כנפיים טונה"
r = requests.get(
    "https://negina.co.il/chords",
    params={"q": query},
    headers=UA,
    timeout=30,
)
print("search status", r.status_code, r.url)
soup = BeautifulSoup(r.text, "html.parser")
for a in soup.find_all("a", href=True):
    href = a["href"]
    text = a.get_text(strip=True)
    if "/chords/" in href and len(href.split("/")) >= 4:
        print(" ", text[:50], href[:90])

# fetch first song
links = [
    a["href"]
    for a in soup.find_all("a", href=True)
    if a["href"].startswith("/chords/") and a["href"].count("/") >= 3
]
if links:
    page_url = urljoin("https://negina.co.il", links[0])
    print("fetching", page_url)
    p = requests.get(page_url, headers=UA, timeout=30)
    psoup = BeautifulSoup(p.text, "html.parser")
    for sel in ["pre", "code", ".chord", "[data-chords]"]:
        el = psoup.select_one(sel)
        if el:
            print(sel, el.get_text()[:300])
    # chord-like content
    text = psoup.get_text("\n")
    for line in text.splitlines()[:80]:
        if re.search(r"\b[A-G][#b]?m?(?:aj|in|7|9)?\b", line) and len(line) < 40:
            print("line", line.strip())
