import re
import requests

url = "https://www.nagnu.co.il/%D7%90%D7%95%D7%9E%D7%A0%D7%99%D7%9D/%D7%99%D7%A6%D7%99%D7%90%D7%AA_%D7%97%D7%99%D7%A8%D7%95%D7%9D/%D7%A7%D7%97%D7%99_%D7%9C%D7%9A_%D7%96%D7%9E%D7%9F/%D7%90%D7%A7%D7%95%D7%A8%D7%93%D7%99%D7%9D"
text = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
for pattern in [
    r"trackId[^\d]+(\d+)",
    r'"track_id"\s*:\s*(\d+)',
    r"track/(\d+)",
    r"chords/(\d+)",
]:
    m = re.search(pattern, text)
    print(pattern, m.group(1) if m else None)

# try build q-data endpoint
for tid in re.findall(r"chords/(\d+)", text):
    api = f"https://www.nagnu.co.il/chords/{tid}"
    r = requests.get(api, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    print("api", api, r.status_code, r.text[:300])
