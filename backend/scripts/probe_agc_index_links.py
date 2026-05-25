import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.all-guitar-chords.com"

r = requests.get(BASE + "/chords/index", headers=UA, timeout=20)
links = sorted(set(re.findall(r'href="(/chords/index/[^"]+)"', r.text)))
print("count", len(links))
for link in links[:80]:
    print(link)

print("--- F/B variants ---")
for link in links:
    if re.search(r"/f|/b|/g|/a|/c|/d|/e", link, re.I):
        if link.count("/") <= 5:
            pass
for link in links:
    parts = link.split("/")
    if len(parts) == 5:
        print(link)
