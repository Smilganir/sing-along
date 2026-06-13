"""Build browser.json from a copied cURL command (full Cookie, no Firefox truncation).

Usage:
  1. Network tab → right-click the browse POST row → Copy as cURL
  2. Paste into backend/data/ytmusic/request.curl (one command, any length)
  3. python scripts/build_ytmusic_auth.py
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import YTMUSIC_AUTH_PATH

CURL_PATH = Path(__file__).resolve().parents[1] / "data" / "ytmusic" / "request.curl"


def _headers_from_curl(raw: str) -> dict[str, str]:
    text = raw.strip()
    if not text:
        raise ValueError("request.curl is empty")

    # Windows paste may use caret continuations; normalize to one line for shlex.
    text = re.sub(r"\^\s*\r?\n", " ", text)
    text = re.sub(r"\\\s*\r?\n", " ", text)

    try:
        parts = shlex.split(text, posix=(sys.platform != "win32"))
    except ValueError as exc:
        raise ValueError(f"Could not parse cURL command: {exc}") from exc

    if not parts or parts[0] != "curl":
        raise ValueError("request.curl must start with curl ...")

    headers: dict[str, str] = {}
    i = 1
    while i < len(parts):
        token = parts[i]
        if token in ("-H", "--header"):
            if i + 1 >= len(parts):
                break
            header = parts[i + 1]
            i += 2
            if ":" not in header:
                continue
            name, value = header.split(":", 1)
            headers[name.strip()] = value.strip()
            continue
        if token.startswith("-") and token not in ("-H", "--header", "--compressed"):
            i += 2 if token in ("-X", "--request", "-d", "--data", "--data-raw") else 1
            continue
        i += 1

    if "Cookie" not in headers and "cookie" not in headers:
        raise ValueError("No Cookie header found in cURL. Copy as cURL from the browse POST row.")
    if "Authorization" not in headers:
        raise ValueError("No Authorization header found in cURL.")

    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() == "cookie":
            normalized["Cookie"] = value
        else:
            normalized[key] = value

    if "x-origin" not in {k.lower() for k in normalized}:
        normalized["x-origin"] = "https://music.youtube.com"

    return normalized


def main() -> None:
    if not CURL_PATH.is_file():
        print(f"Create {CURL_PATH} and paste Copy as cURL output there.", file=sys.stderr)
        raise SystemExit(1)

    raw = CURL_PATH.read_text(encoding="utf-8")
    auth = _headers_from_curl(raw)

    cookie = auth.get("Cookie", "")
    if "…" in cookie or "..." in cookie:
        raise SystemExit("Cookie still truncated. Try Copy as cURL instead of Copy Message.")

    required = ("Cookie", "Authorization")
    missing = [name for name in required if name not in auth]
    if missing:
        raise SystemExit(f"Missing headers: {', '.join(missing)}")

    if "__Secure-3PAPISID" not in cookie:
        print("Warning: Cookie may be incomplete (__Secure-3PAPISID not found).", file=sys.stderr)

    YTMUSIC_AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    YTMUSIC_AUTH_PATH.write_text(json.dumps(auth, indent=2), encoding="utf-8")
    print(f"Wrote {YTMUSIC_AUTH_PATH} ({len(cookie)} char Cookie)")


if __name__ == "__main__":
    main()
