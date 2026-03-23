"""Challenge discovery and parsing from HackyEaster HTML pages."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from lxml import html as lxml_html

from .fetcher import fetch_page

BASE_URL = "https://www.hackyeaster.com/"
CHALLENGE_PATH_RE = re.compile(r"/challenges?/", re.IGNORECASE)


def discover_challenges(*, dynamic: bool = False) -> list[dict]:
    """Scrape HackyEaster site and return a list of challenge dicts."""
    result = fetch_page(BASE_URL, dynamic=dynamic)
    challenges = []

    # Find dedicated challenge page links
    challenge_urls = _find_challenge_links(result.html, BASE_URL)

    # Also probe common index paths
    for index_path in ("/challenges/", "/challenges", "/challenge/"):
        try:
            idx = fetch_page(urljoin(BASE_URL, index_path), dynamic=dynamic)
            if idx.status == 200:
                challenge_urls.update(_find_challenge_links(idx.html, BASE_URL))
        except Exception:
            pass

    if not challenge_urls:
        # No dedicated challenge pages found — parse the main page itself
        ch = _parse_challenge_from_html(result.html, BASE_URL, result.saved_path)
        if ch and ch.get("description", "").strip():
            challenges.append(ch)
    else:
        for url in sorted(challenge_urls):
            try:
                ch_result = fetch_page(url, dynamic=dynamic)
                ch = _parse_challenge_from_html(ch_result.html, url, ch_result.saved_path)
                if ch:
                    challenges.append(ch)
            except Exception as e:
                challenges.append({"id": url, "title": url, "url": url, "error": str(e)})

    return challenges


def parse_challenge_page(url: str, *, dynamic: bool = False) -> dict:
    """Fetch and parse a single challenge page."""
    result = fetch_page(url, dynamic=dynamic)
    ch = _parse_challenge_from_html(result.html, url, result.saved_path)
    return ch or {"id": url, "url": url, "error": "Could not parse challenge content"}


def _find_challenge_links(html: str, base_url: str) -> set[str]:
    if not html.strip():
        return set()
    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return set()
    links = set()
    for href in doc.xpath("//a/@href"):
        absolute = urljoin(base_url, str(href))
        if CHALLENGE_PATH_RE.search(absolute) and absolute.startswith(("http://", "https://")):
            links.add(absolute)
    return links


def _parse_challenge_from_html(html: str, url: str, saved_path: str) -> dict | None:
    if not html.strip():
        return None
    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return None

    # Title
    title_el = doc.find(".//h1")
    if title_el is None:
        title_el = doc.find(".//h2")
    title = title_el.text_content().strip() if title_el is not None else ""
    if not title:
        title_tag = doc.find(".//title")
        title = title_tag.text_content().strip() if title_tag is not None else url

    # Description — full text from main content area
    main = doc.find(".//main") or doc.find(".//article") or doc.find(".//body")
    description = " ".join(main.itertext()).strip() if main is not None else ""

    # Hints
    hints = []
    for el in doc.xpath("//*[contains(@class, 'hint') or contains(@id, 'hint')]"):
        hints.append(el.text_content().strip())

    # Embedded data: code blocks, images, hidden inputs, data attributes
    embedded = {}
    for i, code in enumerate(doc.xpath("//code | //pre")):
        text = code.text_content().strip()
        if text:
            embedded[f"code_block_{i}"] = text
    for i, img in enumerate(doc.xpath("//img")):
        src = img.get("src", "")
        alt = img.get("alt", "")
        if src:
            embedded[f"image_{i}"] = {"src": urljoin(url, src), "alt": alt}
    for i, inp in enumerate(doc.xpath("//input[@type='hidden']")):
        name = inp.get("name", f"hidden_{i}")
        value = inp.get("value", "")
        embedded[f"hidden_input_{name}"] = value

    # Links (for following to sub-resources)
    page_links = []
    for href in doc.xpath("//a/@href"):
        absolute = urljoin(url, str(href))
        if absolute.startswith(("http://", "https://")):
            page_links.append(absolute)

    # Slug from URL or title
    slug = url.rstrip("/").split("/")[-1]
    if not slug or slug in ("", "www.hackyeaster.com"):
        slug = re.sub(r"\W+", "-", title.lower()).strip("-") or "unknown"

    return {
        "id": slug,
        "title": title,
        "url": url,
        "description": description,
        "hints": hints,
        "embedded": embedded,
        "links": page_links[:50],
        "raw_html_path": saved_path,
    }
