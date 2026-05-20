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

r = requests.get("https://negina.co.il/chords", headers=UA, timeout=30)
for m in re.finditer(r"https?://[^\s\"']+", r.text):
    url = m.group(0)
    if "search" in url.lower() or "/api/" in url.lower():
        print(url[:120])

for url in [
    f"https://negina.co.il/api/v1/chords/search?query={quote('כנפיים')}",
    f"https://negina.co.il/api/chords?search={quote('כנפיים')}",
    "https://negina.co.il/chords?q=" + quote("כנפיים"),
]:
    r2 = requests.get(url, headers=UA, timeout=15)
    print(r2.status_code, url[:70], r2.text[:120].replace("\n", " "))

# negina artist search on homepage filter
soup = BeautifulSoup(r.text, "html.parser")
for a in soup.find_all("a", href=True):
    href = a["href"]
    text = a.get_text(strip=True)
    if "/chords/" in href and "טונ" in text.lower() or "tuna" in href.lower():
        print("link", text, href)
