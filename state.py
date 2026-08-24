"""Tracks which articles we've already processed, so nothing is emailed twice.

State is deliberately *not* committed to git. In CI it round-trips through the
GitHub Actions cache; `seen.seed.json` is the committed fallback used on a cold
start so an empty state file can't trigger a full-backlog re-analysis.
"""
import json
import os

from config import SEEN_FILE, SEEN_SEED_FILE


def _read_ids(path: str) -> set[str] | None:
    """Parse a JSON array of ids, or None if the file is missing/unusable."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError, TypeError):
        # Corrupt/unreadable file: treat as absent rather than crash the run.
        return None


def load_seen() -> set[str]:
    """Live state if we have it, else the committed seed, else empty."""
    ids = _read_ids(SEEN_FILE)
    if ids is not None:
        return ids
    seed = _read_ids(SEEN_SEED_FILE)
    if seed is not None:
        print(f"No cached state — bootstrapping from {os.path.basename(SEEN_SEED_FILE)} "
              f"({len(seed)} ids).")
        return seed
    print("No cached state and no seed file — treating every article as new.")
    return set()


def save_seen(seen: set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)
