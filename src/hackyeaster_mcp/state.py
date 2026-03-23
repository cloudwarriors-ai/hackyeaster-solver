"""Challenge attempt tracking via JSON file."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ATTEMPTS_FILE = DATA_DIR / "attempts.json"


def _load() -> list[dict]:
    if not ATTEMPTS_FILE.exists():
        return []
    try:
        return json.loads(ATTEMPTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def log_attempt(
    challenge_id: str,
    answer: str,
    correct: bool,
    notes: str = "",
) -> dict:
    """Record a solve attempt. Returns the logged entry."""
    entries = _load()
    entry = {
        "challenge_id": challenge_id,
        "answer": answer,
        "correct": correct,
        "notes": notes,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    entries.append(entry)
    _save(entries)
    return entry


def get_progress() -> dict:
    """Return all attempts grouped by challenge, plus summary."""
    entries = _load()
    by_challenge: dict[str, list[dict]] = {}
    for e in entries:
        by_challenge.setdefault(e["challenge_id"], []).append(e)

    solved = [cid for cid, attempts in by_challenge.items() if any(a["correct"] for a in attempts)]

    return {
        "total_attempts": len(entries),
        "challenges_attempted": len(by_challenge),
        "challenges_solved": len(solved),
        "solved_ids": solved,
        "by_challenge": by_challenge,
    }


def get_solved() -> list[str]:
    """Return list of solved challenge IDs."""
    return get_progress()["solved_ids"]
