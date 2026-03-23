"""Scrapling-backed fetcher for HackyEaster pages.

Adapted from zoom_slm_orchestration/services/kb_ingest/crawl_adapter.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from scrapling import DynamicFetcher, Fetcher

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_HTML_DIR = DATA_DIR / "raw_html"


@dataclass
class FetchResult:
    html: str
    status: int
    final_url: str
    saved_path: str


def _response_text(response) -> str:
    """Extract text from Scrapling response with fallbacks.

    Matches the pattern from zoom crawl_adapter.py lines 52-61.
    """
    text = getattr(response, "text", "") or ""
    if text:
        return text
    html_content = getattr(response, "html_content", b"")
    if isinstance(html_content, bytes):
        return html_content.decode("utf-8", errors="ignore")
    if html_content:
        return str(html_content)
    return ""


def fetch_page(url: str, *, dynamic: bool = False, raw_dir: Path | None = None) -> FetchResult:
    """Fetch a URL with Scrapling, persist raw HTML, return structured result.

    Uses Fetcher.get for static pages. When dynamic=True or static fetch yields
    very little content, retries with DynamicFetcher.fetch(network_idle=True).
    """
    raw_dir = raw_dir or RAW_HTML_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    if dynamic:
        response = DynamicFetcher.fetch(url, network_idle=True)
    else:
        response = Fetcher.get(url, verify=False)

    text = _response_text(response)

    # Auto-escalate to dynamic if static fetch returned almost nothing
    if not dynamic and len(text.strip()) < 200:
        try:
            response = DynamicFetcher.fetch(url, network_idle=True)
            text = _response_text(response)
        except Exception:
            pass  # keep the static result

    status = int(getattr(response, "status", 0) or 0)
    final_url = str(getattr(response, "url", url))
    save_path = raw_dir / f"{uuid4().hex[:12]}.html"
    save_path.write_text(text, encoding="utf-8")

    return FetchResult(
        html=text,
        status=status,
        final_url=final_url,
        saved_path=str(save_path),
    )


def download_bytes(url: str) -> bytes:
    """Download raw bytes from a URL (for images, files)."""
    response = Fetcher.get(url, verify=False)
    raw = getattr(response, "content", b"")
    if isinstance(raw, bytes):
        return raw
    text = _response_text(response)
    return text.encode("utf-8")
