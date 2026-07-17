"""Fetches Substack articles from RSS feeds and normalizes them."""
import html
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from config import FEEDS, MAX_AGE_DAYS, MIN_ARTICLE_CHARS

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]*\n[ \t]*")


@dataclass
class Article:
    id: str          # stable unique key for dedup
    title: str
    author: str
    url: str
    feed: str
    published: str    # human-readable
    text: str         # plain-text body


def _strip_html(raw: str) -> str:
    """Turn RSS HTML into readable plain text (good enough for an LLM)."""
    if not raw:
        return ""
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6])\s*/?>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub("\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _best_body(entry) -> str:
    """Substack usually puts the full post in content:encoded; fall back to summary."""
    if getattr(entry, "content", None):
        raw = max((c.get("value", "") for c in entry.content), key=len, default="")
        if raw:
            return _strip_html(raw)
    return _strip_html(getattr(entry, "summary", "") or "")


def _published(entry) -> tuple[datetime | None, str]:
    struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not struct:
        return None, "unknown date"
    dt = datetime.fromtimestamp(time.mktime(struct), tz=timezone.utc)
    return dt, dt.strftime("%Y-%m-%d")


def fetch_new_articles(seen: set[str]) -> list[Article]:
    """Return unseen, recent, non-trivial articles across all configured feeds."""
    cutoff = datetime.now(timezone.utc).timestamp() - MAX_AGE_DAYS * 86400
    articles: list[Article] = []

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        feed_title = parsed.feed.get("title", feed_url)
        if parsed.bozo and not parsed.entries:
            print(f"  ! could not read feed: {feed_url} ({parsed.bozo_exception})")
            continue

        for entry in parsed.entries:
            uid = entry.get("id") or entry.get("link")
            if not uid or uid in seen:
                continue

            dt, when = _published(entry)
            if dt and dt.timestamp() < cutoff:
                continue

            body = _best_body(entry)
            if len(body) < MIN_ARTICLE_CHARS:
                # Too short to judge (likely a paywall teaser); mark seen and skip.
                seen.add(uid)
                continue

            articles.append(Article(
                id=uid,
                title=entry.get("title", "(untitled)"),
                author=entry.get("author", feed_title),
                url=entry.get("link", ""),
                feed=feed_title,
                published=when,
                text=body,
            ))

    return articles
