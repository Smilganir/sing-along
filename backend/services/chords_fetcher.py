import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from requests import Request

from services.http_cache import get_http_session

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
HTTP = get_http_session()


@dataclass
class ChordSheetResult:
    content: str
    source: str
    source_url: str
    has_chords: bool


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def hebrew_path_slug(value: str) -> str:
    from urllib.parse import quote

    cleaned = clean_title_for_search(value).replace(" ", "-")
    return quote(cleaned, safe="")


def _cache_key_url(url: str, params: dict | None = None) -> str:
    prepared = Request("GET", url, params=params or {}).prepare()
    return prepared.url


def candidate_cache_urls(title: str, artist: str, language: str) -> list[str]:
    """URLs that scrapers may cache for a given song lookup."""
    clean_title = clean_title_for_search(title, artist)
    clean_artist = clean_artist_name(artist)
    urls: list[str] = []

    urls.append(
        _cache_key_url(
            "https://lrclib.net/api/search",
            {"track_name": clean_title, "artist_name": clean_artist},
        )
    )

    if language == "he":
        query = f"{clean_title} {search_artist_name(artist)}".strip()
        urls.append(
            _cache_key_url(
                "https://www.tab4u.com/resultsSimple",
                {"tab": "songs", "q": query},
            )
        )
        urls.append(
            _cache_key_url(
                "https://www.nagnu.co.il/",
                {"go": "search", "search": query},
            )
        )
        artist_slug = hebrew_path_slug(clean_artist)
        title_slug = hebrew_path_slug(clean_title)
        urls.append(f"https://negina.co.il/chords/{artist_slug}/{title_slug}")
        urls.append(_cache_key_url("https://negina.co.il/chords", {"q": query}))
    else:
        artist_slug = slugify(clean_artist)
        title_slug = slugify(clean_title)
        if artist_slug and title_slug:
            urls.append(f"https://www.e-chords.com/chords/{artist_slug}/{title_slug}")

    return urls


def fetch_echords(title: str, artist: str) -> ChordSheetResult | None:
    artist_slug = slugify(clean_artist_name(artist))
    title_slug = slugify(clean_title_for_search(title, artist))
    if not artist_slug or not title_slug:
        return None

    url = f"https://www.e-chords.com/chords/{artist_slug}/{title_slug}"
    response = HTTP.get(url, headers=HEADERS, timeout=30)
    if not response.ok:
        return None

    pre = BeautifulSoup(response.text, "html.parser").find("pre")
    if not pre:
        return None

    content = pre.get_text("\n").strip()
    if len(content) < 40:
        return None

    return ChordSheetResult(
        content=content,
        source="echords",
        source_url=url,
        has_chords=_looks_like_chords(content),
    )


def fetch_tab4u(title: str, artist: str) -> ChordSheetResult | None:
    search_artist = resolve_search_artist(title, artist)
    query = f"{clean_title_for_search(title, artist)} {search_artist}".strip()
    search = HTTP.get(
        "https://www.tab4u.com/resultsSimple",
        params={"tab": "songs", "q": query},
        headers=HEADERS,
        timeout=30,
    )
    if not search.ok:
        return None

    href = _pick_tab4u_href(BeautifulSoup(search.text, "html.parser"), title, artist)
    if not href:
        return None

    page_url = urljoin("https://www.tab4u.com/", href.lstrip("/"))
    page = HTTP.get(page_url, headers=HEADERS, timeout=30)
    if not page.ok:
        return None

    content = _extract_tab4u_content(BeautifulSoup(page.text, "html.parser"))
    if len(content) < 40:
        return None

    return ChordSheetResult(
        content=content,
        source="tab4u",
        source_url=page_url,
        has_chords=_looks_like_chords(content),
    )


def fetch_negina(title: str, artist: str) -> ChordSheetResult | None:
    artist_slug = hebrew_path_slug(clean_artist_name(artist))
    title_slug = hebrew_path_slug(clean_title_for_search(title, artist))
    page_url = f"https://negina.co.il/chords/{artist_slug}/{title_slug}"
    page = HTTP.get(page_url, headers=HEADERS, timeout=30)
    if not page.ok:
        page_url = _find_negina_search_url(title, artist)
        if not page_url:
            return None
        page = HTTP.get(page_url, headers=HEADERS, timeout=30)
        if not page.ok:
            return None

    content = _extract_negina_content(BeautifulSoup(page.text, "html.parser"))
    if len(content) < 20:
        return None

    return ChordSheetResult(
        content=content,
        source="negina",
        source_url=page_url,
        has_chords=_looks_like_chords(content),
    )


def fetch_nagnu(title: str, artist: str) -> ChordSheetResult | None:
    query = f"{clean_title_for_search(title, artist)} {search_artist_name(artist)}".strip()
    search = HTTP.get(
        "https://www.nagnu.co.il/",
        params={"go": "search", "search": query},
        headers=HEADERS,
        timeout=30,
    )
    if not search.ok:
        return None

    soup = BeautifulSoup(search.text, "html.parser")
    href = None
    title_key = clean_title_for_search(title, artist).replace(" ", "")
    artist_keys = _artist_match_keys(artist)

    for link in soup.select("a[href]"):
        candidate = link.get("href", "")
        if not candidate.startswith("/%D7%90%D7%95%D7%9E%D7%A0%D7%99%D7%9D/"):
            continue
        if not candidate.endswith("%D7%90%D7%A7%D7%95%D7%A8%D7%93%D7%99%D7%9D"):
            continue
        label = link.get_text(strip=True).replace(" ", "")
        if title_key[:4] not in label:
            continue
        if artist_keys and not any(key[:3] in label for key in artist_keys):
            continue
        href = candidate
        break

    if not href:
        return None

    page_url = urljoin("https://www.nagnu.co.il", href)
    page = HTTP.get(page_url, headers=HEADERS, timeout=30)
    if not page.ok:
        return None

    text = _extract_nagnu_visible_text(BeautifulSoup(page.text, "html.parser"))
    if len(text) < 80:
        return None

    return ChordSheetResult(
        content=text,
        source="nagnu",
        source_url=page_url,
        has_chords=_looks_like_chords(text),
    )


ALLOWED_CHORD_HOSTS: dict[str, str] = {
    "www.tab4u.com": "tab4u",
    "tab4u.com": "tab4u",
    "www.e-chords.com": "echords",
    "e-chords.com": "echords",
    "negina.co.il": "negina",
    "www.negina.co.il": "negina",
    "www.nagnu.co.il": "nagnu",
    "nagnu.co.il": "nagnu",
    "tabs.ultimate-guitar.com": "ultimate_guitar",
    "www.ultimate-guitar.com": "ultimate_guitar",
    "ultimate-guitar.com": "ultimate_guitar",
    "guitartuna.com": "guitartuna",
    "www.guitartuna.com": "guitartuna",
}

UG_HOSTS = frozenset(
    {
        "tabs.ultimate-guitar.com",
        "www.ultimate-guitar.com",
        "ultimate-guitar.com",
    }
)


def _is_ultimate_guitar_host(host: str) -> bool:
    host = host.lower()
    return host in UG_HOSTS or host.endswith(".ultimate-guitar.com")


def _is_guitartuna_host(host: str) -> bool:
    host = host.lower().split(":", 1)[0]
    return host in {"guitartuna.com", "www.guitartuna.com"} or host.endswith(".guitartuna.com")


def _resolve_chord_source(host: str) -> str | None:
    host = host.lower().split(":", 1)[0]
    if host in ALLOWED_CHORD_HOSTS:
        return ALLOWED_CHORD_HOSTS[host]
    if _is_ultimate_guitar_host(host):
        return "ultimate_guitar"
    if _is_guitartuna_host(host):
        return "guitartuna"
    return None


def _fetch_with_curl_cffi(url: str) -> tuple[str, str, int] | None:
    """Try curl_cffi with browser TLS impersonation. Returns (text, url, status) or None."""
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return None
    try:
        response = curl_requests.get(url, impersonate="chrome", timeout=30)
    except Exception:
        return None
    final_url = str(response.url).split("#", 1)[0]
    return response.text, final_url, response.status_code


def _fetch_page_html(source_url: str) -> tuple[str, str]:
    """Fetch a chord/lyrics page, defeating bot-detection 403s common on datacenter IPs.

    Strategy: always try curl_cffi first (mimics real Chrome TLS/JA3 fingerprint),
    fall back to the cached requests session if curl_cffi is unavailable or errors.
    Ultimate Guitar requires curl_cffi, so for that host we never fall back.
    """
    url = source_url.strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    curl_result = _fetch_with_curl_cffi(url)

    if curl_result is None and _is_ultimate_guitar_host(host):
        raise ValueError(
            "Ultimate Guitar support requires curl_cffi (pip install curl_cffi)"
        )

    if curl_result is not None:
        text, final_url, status = curl_result
        if 200 <= status < 400:
            return text, final_url
        if _is_ultimate_guitar_host(host):
            raise ValueError(f"Could not fetch page (HTTP {status})")

    response = HTTP.get(url, headers=HEADERS, timeout=30)
    if not response.ok:
        raise ValueError(f"Could not fetch page (HTTP {response.status_code})")
    final_url = response.url.split("#", 1)[0]
    return response.text, final_url


def _convert_ug_wiki_content(raw: str) -> str:
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        stripped = re.sub(r"\[/?tab\]", "", stripped)
        section = re.fullmatch(r"\[([^\]]+)\]", stripped)
        if section and not section.group(1).startswith("ch"):
            lines.append(f"{section.group(1)}:")
            continue

        if "[ch]" in stripped:
            chords = re.findall(r"\[ch\]([^\[]+?)\[/ch\]", stripped)
            lyrics = re.sub(r"\[ch\][^\[]+?\[/ch\]", "", stripped)
            lyrics = re.sub(r"\[[^\]]+\]", "", lyrics)
            lyrics = re.sub(r"\s+", " ", lyrics).strip()
            if chords:
                lines.append("  ".join(chords))
            if lyrics:
                lines.append(lyrics)
            continue

        lines.append(stripped)

    return "\n".join(lines).strip()


def _extract_ultimate_guitar_content(html: str) -> str:
    match = re.search(r'data-content="([^"]+)"', html)
    if not match:
        raise ValueError("Could not parse Ultimate Guitar page")

    payload = json.loads(unescape(match.group(1)))
    wiki = (
        payload.get("store", {})
        .get("page", {})
        .get("data", {})
        .get("tab_view", {})
        .get("wiki_tab", {})
    )
    raw = wiki.get("content", "") if isinstance(wiki, dict) else ""
    if len(raw) < 40:
        raise ValueError("Ultimate Guitar tab had no content")

    return _convert_ug_wiki_content(raw)


def _guitartuna_line_content(line_el) -> tuple[list[str], str]:
    chords = [
        node.get_text(strip=True)
        for node in line_el.select(".chordLabel")
        if node.get_text(strip=True)
    ]
    clone = BeautifulSoup(str(line_el), "html.parser")
    for node in clone.select(".fretBoard, svg, .brugml, .eIHNEE, .chordLabel"):
        node.decompose()

    text = clone.get_text(" ", strip=True)
    for chord in chords:
        text = re.sub(rf"^{re.escape(chord)}\s*", "", text)
        text = re.sub(rf"\s*{re.escape(chord)}\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return chords, text


def _extract_guitartuna_content(soup: BeautifulSoup) -> str:
    root = soup.select_one('[data-testid="song-lyrics"]') or soup.find(id="songcontent")
    if not root:
        raise ValueError("Could not parse GuitarTuna page")

    lines: list[str] = []
    for block in root.select(".partContainer, div.line[data-bar]"):
        part_title = block.select_one(".part_type")
        if part_title:
            title = part_title.get_text(strip=True)
            if title:
                lines.append(f"{title}:")
            continue

        chords, text = _guitartuna_line_content(block)
        if chords:
            lines.append("  ".join(chords))
        if text:
            lines.append(text)

    content = "\n".join(lines).strip()
    if len(content) < 40:
        raise ValueError("GuitarTuna page had too little chord or lyric content")
    return content


def fetch_chords_from_url(source_url: str) -> ChordSheetResult:
    """Fetch chord sheet content from a known lyrics/chords site URL."""
    normalized = source_url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL")

    host = parsed.netloc.lower().split(":", 1)[0]
    source = _resolve_chord_source(host)
    if not source:
        raise ValueError(
            "Unsupported source — use Tab4U, Ultimate Guitar, GuitarTuna, e-chords, Negina, or Nagnu"
        )

    html, page_url = _fetch_page_html(normalized)
    soup = BeautifulSoup(html, "html.parser")

    if source == "tab4u":
        content = _extract_tab4u_content(soup)
    elif source == "echords":
        pre = soup.find("pre")
        content = pre.get_text("\n").strip() if pre else ""
    elif source == "negina":
        content = _extract_negina_content(soup)
    elif source == "ultimate_guitar":
        content = _extract_ultimate_guitar_content(html)
    elif source == "guitartuna":
        content = _extract_guitartuna_content(soup)
    else:
        content = _extract_nagnu_visible_text(soup)

    if len(content) < 40:
        raise ValueError("Page had too little chord or lyric content")

    return ChordSheetResult(
        content=content,
        source=source,
        source_url=page_url,
        has_chords=_looks_like_chords(content),
    )


def _collect_chord_results(
    title: str,
    artist: str,
    fetchers: tuple,
) -> ChordSheetResult | None:
    lyrics_fallback: ChordSheetResult | None = None
    for fetcher in fetchers:
        try:
            result = fetcher(title, artist)
        except Exception:
            result = None
        if not result or len(result.content) < 40:
            continue
        if result.has_chords:
            return result
        if lyrics_fallback is None or len(result.content) > len(lyrics_fallback.content):
            lyrics_fallback = result
    return lyrics_fallback


def _pick_ultimate_guitar_url(html: str, title: str, artist: str) -> str | None:
    title_key = slugify(clean_title_for_search(title, artist))
    artist_key = slugify(clean_artist_name(artist))
    if len(title_key) < 3:
        return None

    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"https://tabs\.ultimate-guitar\.com/tab/[^\s\"'<>]+", html):
        url = unescape(match.group(0)).split("&quot;")[0].split('"')[0].rstrip("\\")
        slug = url.rsplit("/", 1)[-1].lower()
        if title_key[:4] not in slug.replace("-", ""):
            continue
        score = 2
        if artist_key and artist_key[:3] in slug.replace("-", ""):
            score += 3
        if "-chords-" in slug:
            score += 2
        candidates.append((score, url))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return candidates[0][1]


def fetch_ultimate_guitar(title: str, artist: str) -> ChordSheetResult | None:
    from urllib.parse import quote

    query = quote(f"{clean_title_for_search(title, artist)} {clean_artist_name(artist)}".strip())
    search_url = f"https://www.ultimate-guitar.com/search.php?search_type=title&value={query}"
    html, _ = _fetch_page_html(search_url)
    tab_url = _pick_ultimate_guitar_url(html, title, artist)
    if not tab_url:
        return None
    return fetch_chords_from_url(tab_url)


def fetch_guitartuna(title: str, artist: str) -> ChordSheetResult | None:
    query = f"{clean_title_for_search(title, artist)} {clean_artist_name(artist)}".strip()
    response = HTTP.get(
        "https://guitartuna.com/chords",
        params={"search": query},
        headers=HEADERS,
        timeout=30,
    )
    if not response.ok:
        return None

    title_key = slugify(clean_title_for_search(title, artist))
    artist_key = slugify(clean_artist_name(artist))
    if len(title_key) < 3:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/chords/" not in href or "easy-guitar-chords" not in href:
            continue
        slug = href.split("/chords/")[-1].split("?")[0].lower()
        if title_key[:4] not in slug.replace("-", ""):
            continue
        if artist_key and artist_key[:3] not in slug.replace("-", ""):
            continue
        page_url = urljoin("https://guitartuna.com", href)
        return fetch_chords_from_url(page_url)
    return None


def fetch_chords(title: str, artist: str, language: str) -> ChordSheetResult | None:
    if language == "he":
        return _collect_chord_results(
            title,
            artist,
            (fetch_tab4u, fetch_nagnu, fetch_negina, fetch_ultimate_guitar, fetch_guitartuna),
        )
    return _collect_chord_results(
        title,
        artist,
        (fetch_echords, fetch_ultimate_guitar, fetch_guitartuna),
    )


def clean_artist_name(artist: str) -> str:
    name = artist.replace(" - Topic", "").strip()
    if "," in name:
        name = name.split(",")[0].strip()
    return name


# Romanized / YouTube artist names → Hebrew search names for local chord sites.
ARTIST_SEARCH_ALIASES: dict[str, str] = {
    "svika pick": "צביקה פיק",
}

GENERIC_TITLE_PREFIXES = frozenset(
    {
        "מוסיקה",
        "music",
        "שיר",
        "song",
        "audio",
        "video",
    }
)


def search_artist_name(artist: str) -> str:
    name = clean_artist_name(artist)
    return ARTIST_SEARCH_ALIASES.get(name.lower(), name)


def _artist_match_keys(artist: str) -> list[str]:
    keys: list[str] = []
    for name in (clean_artist_name(artist), search_artist_name(artist)):
        key = name.replace(" ", "")
        if key and key not in keys:
            keys.append(key)
    return keys


TITLE_SUFFIX_RE = re.compile(
    r"(?:"
    r"\(\s*"
    r"(?:"
    r"official\s+(?:music\s+)?video|"
    r"official\s+video|"
    r"official\s+audio|"
    r"official\s+lyric\s+video|"
    r"lyric\s+video|"
    r"live(?:\s+\d{4})?|"
    r"remaster(?:ed)?(?:\s+\d{4})?|"
    r"\d{4}\s+mix|"
    r"\d{4}\s+remaster|"
    r"from\s+[\"'].*?[\"']\s+soundtrack|"
    r"single\s+version|"
    r"album\s+version|"
    r"acoustic(?:\s+version)?|"
    r"extended\s+version|"
    r"radio\s+edit|"
    r"visual(?:izer)?|"
    r"hd\s+video|"
    r"4k\s+video"
    r")"
    r"(?:\s*/\s*[^)]*)?"
    r"\s*\)"
    r"|"
    r"\[\s*"
    r"(?:"
    r"lyrics?|"
    r"official\s+video|"
    r"hd|"
    r"4k|"
    r"מילים"
    r")"
    r"\s*\]"
    r")",
    re.IGNORECASE,
)


def clean_title_for_search(title: str, artist: str | None = None) -> str:
    """Strip YouTube/metadata noise so chord and lyric searches hit the core song name."""
    cleaned = title.strip().strip("\"'")
    if not cleaned:
        return title

    if artist:
        artist_clean = clean_artist_name(artist)
        if artist_clean:
            for sep in (" - ", " – ", " — "):
                prefix = f"{artist_clean}{sep}"
                if cleaned.lower().startswith(prefix.lower()):
                    cleaned = cleaned[len(prefix) :].strip()
                    break
            colon_prefix = f"{artist_clean}: "
            if cleaned.lower().startswith(colon_prefix.lower()):
                cleaned = cleaned[len(colon_prefix) :].strip()

    title_artist = _artist_from_title_prefix(cleaned)
    if title_artist:
        for sep in (" - ", " – ", " — "):
            prefix = f"{title_artist}{sep}"
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                break

    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = TITLE_SUFFIX_RE.sub(" ", cleaned)

    subtitle = _extract_parenthetical_title(cleaned)
    if subtitle:
        cleaned = subtitle
    else:
        cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—:|")

    return cleaned or title


def _extract_parenthetical_title(title: str) -> str | None:
    """YouTube often labels songs as 'מוסיקה (מעלה מעלה)' — prefer the inner title."""
    match = re.search(r"\(([^)]+)\)\s*$", title.strip())
    if not match:
        return None
    inner = match.group(1).strip()
    before = title[: match.start()].strip()
    outer = before.rsplit(" - ", 1)[-1].strip() if " - " in before else before
    if not inner:
        return None
    if outer.lower() in GENERIC_TITLE_PREFIXES or len(inner) >= len(outer):
        return inner
    return None


def _artist_from_title_prefix(title: str) -> str | None:
    for sep in (" - ", " – ", " — "):
        if sep not in title:
            continue
        prefix = title.split(sep, 1)[0].strip()
        if len(prefix) >= 3 and re.search(r"[\u0590-\u05FFa-zA-Z]", prefix):
            return prefix
    return None


def resolve_search_artist(title: str, artist: str) -> str:
    from_title = _artist_from_title_prefix(title)
    if from_title:
        return search_artist_name(from_title)
    return search_artist_name(artist)


def _pick_tab4u_href(soup: BeautifulSoup, title: str, artist: str) -> str | None:
    title_key = clean_title_for_search(title, artist).replace(" ", "")
    artist_keys = _artist_match_keys(resolve_search_artist(title, artist))
    candidates: list[tuple[int, str]] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "tabs/songs/" not in href:
            continue
        label = link.get_text(strip=True).replace(" ", "")
        if "ללאאקורדים" in label:
            continue
        if len(title_key) < 4:
            if title_key not in label:
                continue
        elif title_key[:4] not in label:
            continue
        score = 2
        for artist_key in artist_keys:
            if artist_key[:3] in label:
                score += 3
                break
            if artist_key[:3] in href.replace("%", ""):
                score += 2
                break
        candidates.append((score, href))

    if not candidates:
        return None
    candidates.sort(key=lambda item: -item[0])
    return candidates[0][1]


def _find_negina_search_url(title: str, artist: str) -> str | None:
    query = f"{clean_title_for_search(title, artist)} {search_artist_name(artist)}".strip()
    search = HTTP.get(
        "https://negina.co.il/chords",
        params={"q": query},
        headers=HEADERS,
        timeout=30,
    )
    if not search.ok:
        return None

    soup = BeautifulSoup(search.text, "html.parser")
    title_key = clean_title_for_search(title, artist).replace(" ", "")
    artist_keys = _artist_match_keys(artist)

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith("/chords/") or href.count("/") < 3:
            continue
        text = link.get_text(strip=True).replace(" ", "")
        if title_key[:4] not in text:
            continue
        if artist_keys and not any(key[:3] in text for key in artist_keys):
            continue
        return urljoin("https://negina.co.il", href)
    return None


def _extract_tab4u_content(soup: BeautifulSoup) -> str:
    el = soup.find(id="songContentTPL")
    if not el:
        return ""

    lines: list[str] = []
    for line in el.get_text("\n").splitlines():
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _negina_phrase_lyric(phrase) -> str:
    lyric = phrase.select_one(".lyric")
    if not lyric:
        return ""
    for gutter in lyric.select(".gutter"):
        gutter.decompose()
    return re.sub(r"\s+", " ", lyric.get_text(strip=True))


def _negina_phrase_chord(phrase) -> str | None:
    chord = phrase.select_one(".chord")
    if not chord:
        return None
    text = chord.get_text(strip=True)
    if text in {"+", "−", "0", ""}:
        return None
    return text


def _build_negina_chord_line(parts: list[tuple[str | None, str]]) -> str:
    lyric = "".join(fragment for _, fragment in parts)
    chords = [chord for chord, _ in parts if chord]

    if not lyric.strip() and chords:
        return " ".join(chords)

    placements: list[tuple[int, str]] = []
    position = 0

    for chord, fragment in parts:
        if chord:
            placements.append((position, chord))
        if fragment:
            position += len(fragment)
        elif chord:
            position += len(chord) + 1

    if not placements:
        return ""

    end = len(lyric)
    for start, chord in placements:
        end = max(end, start + len(chord))
    slots = [" "] * end

    for start, chord in placements:
        while start < len(slots) and any(
            slots[index] != " "
            for index in range(start, min(start + len(chord), len(slots)))
        ):
            start += 1
        needed = start + len(chord)
        if needed > len(slots):
            slots.extend([" "] * (needed - len(slots)))
        for offset, char in enumerate(chord):
            index = start + offset
            if index < len(slots):
                slots[index] = char

    return "".join(slots).rstrip()


def _negina_flush_line(parts: list[tuple[str | None, str]], lines: list[str]) -> None:
    if not parts:
        return

    lyric = "".join(fragment for _, fragment in parts).strip()
    has_chords = any(chord for chord, _ in parts if chord)
    if not lyric and not has_chords:
        return

    if has_chords:
        chord_line = _build_negina_chord_line(parts)
        if chord_line.strip():
            lines.append(chord_line)
    if lyric:
        lines.append(lyric)


def _extract_negina_content(soup: BeautifulSoup) -> str:
    page = soup.select_one(".song-page-new") or soup
    container = page.select_one(".song-text__wrp") or page
    phrases = container.select(".phrase")
    if not phrases:
        return ""

    lines: list[str] = []
    current: list[tuple[str | None, str]] = []

    for phrase in phrases:
        classes = phrase.get("class", [])
        chord = _negina_phrase_chord(phrase)
        lyric = _negina_phrase_lyric(phrase)
        is_join = "join" in classes
        is_no_lyric = "noLyric" in classes

        if is_no_lyric and not lyric.strip():
            if chord:
                if current and all(existing_chord is None for existing_chord, _ in current):
                    _negina_flush_line(current, lines)
                    current = []
                current.append((chord, ""))
            continue

        if not is_join and current:
            _negina_flush_line(current, lines)
            current = []

        current.append((chord, lyric))

    _negina_flush_line(current, lines)
    return "\n".join(lines).strip()


def _looks_like_chords(content: str) -> bool:
    if re.search(r"\[[A-G][#b]?[^\]]*\]", content):
        return True
    return bool(
        re.search(
            r"(^|\n|\s)([A-G][#b]?(?:maj|min|m|sus|add|dim|aug)?[0-9]?(?:maj7|m7|7)?(?:/[A-G][#b]?)?)\s*($|\n)",
            content,
            re.MULTILINE,
        )
    )


def _extract_nagnu_visible_text(soup: BeautifulSoup) -> str:
    for node in soup.select("form, script, style, nav, header, footer"):
        node.decompose()

    lines: list[str] = []
    for line in soup.get_text("\n").splitlines():
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if stripped in {
            "אקורדים",
            "עורך טקסט",
            "עורך חכם",
            "תצוגה מקדימה",
            "רווח שורות",
            "שינוי טון",
        }:
            continue
        if "הסר פרסומות" in stripped or "Landscape" in stripped:
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    start = text.find("[")
    if start == -1:
        start = text.find("פזמון")
    if start == -1:
        return ""
    return text[start:].strip()
