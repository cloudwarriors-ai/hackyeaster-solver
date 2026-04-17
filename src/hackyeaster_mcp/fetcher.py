"""Scrapling-backed fetcher for HackyEaster pages.

Adapted from zoom_slm_orchestration/services/kb_ingest/crawl_adapter.py.

Authenticated endpoints use a lazily-initialised requests.Session that logs
in via the HackyEaster API and caches the session for the process lifetime.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import requests
from scrapling import DynamicFetcher, Fetcher

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_HTML_DIR = DATA_DIR / "raw_html"

# ── Credentials / auth session ────────────────────────────────────────────────

_SESSION: requests.Session | None = None
_SESSION_LOCK = threading.Lock()

LOGIN_URL = "https://26.hackyeaster.com/app/auth/login"


def _load_env() -> dict[str, str]:
    """Parse KEY=VALUE pairs from .env files in the project tree.

    Searches upward from this file's location until it finds a .env or hits
    the filesystem root.  Returns an empty dict if none is found.
    """
    env: dict[str, str] = {}
    candidate = Path(__file__).resolve()
    for _ in range(10):
        candidate = candidate.parent
        env_file = candidate / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
            break
        if candidate == candidate.parent:
            break
    return env


def get_session() -> requests.Session:
    """Return a logged-in requests.Session, logging in lazily on first call."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            return _SESSION
        env = _load_env()
        username = env.get("username", "")
        password = env.get("password", "")
        session = requests.Session()
        if username and password:
            resp = session.post(
                LOGIN_URL,
                data={"username": username, "password": password},
                timeout=30,
                verify=False,
            )
            resp.raise_for_status()
        _SESSION = session
    return _SESSION


# ── Scrapling helpers (unchanged public API) ──────────────────────────────────


@dataclass
class FetchResult:
    html: str
    status: int
    final_url: str
    saved_path: str


@dataclass
class DownloadResult:
    body: bytes
    status: int
    final_url: str
    content_type: str


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


def _response_bytes(response) -> bytes:
    """Extract raw bytes from Scrapling response objects with fallbacks."""
    for attr in ("content", "body", "_raw_body"):
        raw = getattr(response, attr, b"")
        if isinstance(raw, bytes) and raw:
            return raw
        if isinstance(raw, bytearray) and raw:
            return bytes(raw)

    html_content = getattr(response, "html_content", b"")
    if isinstance(html_content, bytes) and html_content:
        return html_content
    if isinstance(html_content, str) and html_content:
        encoding = getattr(response, "encoding", None) or "utf-8"
        return html_content.encode(encoding, errors="ignore")

    text = getattr(response, "text", "") or ""
    if text:
        encoding = getattr(response, "encoding", None) or "utf-8"
        return text.encode(encoding, errors="ignore")

    return b""


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


def download_resource(url: str) -> DownloadResult:
    """Download a URL and preserve byte/body metadata for downstream tools."""
    response = Fetcher.get(url, verify=False)
    headers = getattr(response, "headers", {}) or {}
    return DownloadResult(
        body=_response_bytes(response),
        status=int(getattr(response, "status", 0) or 0),
        final_url=str(getattr(response, "url", url)),
        content_type=str(headers.get("content-type", "")),
    )


def download_bytes(url: str) -> bytes:
    """Download raw bytes from a URL (for images, files)."""
    return download_resource(url).body


# ── Authenticated REST helpers ────────────────────────────────────────────────


def auth_get(url: str, **kwargs) -> requests.Response:
    """GET via the authenticated session."""
    return get_session().get(url, timeout=30, verify=False, **kwargs)


def auth_post(url: str, **kwargs) -> requests.Response:
    """POST via the authenticated session."""
    return get_session().post(url, timeout=30, verify=False, **kwargs)
