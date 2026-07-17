"""Tracks which articles we've already processed, so nothing is emailed twice."""
import json
import os

from config import SEEN_FILE


def load_seen() -> set[str]:
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        # Corrupt/unreadable file: treat as empty rather than crash the run.
        return set()


def save_seen(seen: set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)
