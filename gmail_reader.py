"""Reads Substack posts straight from your Gmail (IMAP), so the source of truth
is your actual inbox — subscribe to anything on Substack and it flows in here,
no feed list to maintain. Reuses GMAIL_ADDRESS / GMAIL_APP_PASSWORD."""
import email
import imaplib
import os
import re
from datetime import datetime, timedelta, timezone
from email.policy import default as default_policy

from config import GMAIL_LABEL, MAX_AGE_DAYS, MIN_ARTICLE_CHARS
from feed_reader import Article, _strip_html  # reuse the shared model + HTML cleaner

# A real post email always links to the post at /p/<slug>; notifications/system
# mail generally don't in the same way. We use this both to find the canonical
# URL and as a signal that the message is an actual article.
_POST_URL_RE = re.compile(r"https?://[^\s\"'<>]+/p/[a-zA-Z0-9\-]+")


def _extract_post_url(html: str) -> str:
    """First clean article URL in the email, minus tracking query params."""
    match = _POST_URL_RE.search(html)
    if not match:
        return ""
    return match.group(0).split("?", 1)[0]


def _body_html(msg) -> str:
    body = msg.get_body(preferencelist=("html", "plain"))
    if body is None:
        return ""
    content = body.get_content()
    return content if body.get_content_type() == "text/plain" else content


def fetch_new_articles(seen: set[str]) -> list[Article]:
    """Return unseen, recent Substack post emails from the configured label."""
    address = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not address or not password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set to read the inbox")

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(address, password.replace(" ", ""))
    except imaplib.IMAP4.error as e:
        raise RuntimeError(
            f"Gmail IMAP login failed for {address}: {e}. "
            "Check GMAIL_APP_PASSWORD is a valid Google App Password (not your normal password)."
        ) from e
    try:
        status, _ = imap.select(f'"{GMAIL_LABEL}"', readonly=True)
        if status != "OK":
            _, folders = imap.list()
            names = ", ".join(f.decode(errors="replace").split(' "/" ')[-1] for f in folders)
            raise RuntimeError(
                f'Gmail label/folder "{GMAIL_LABEL}" not found. Available: {names}\n'
                "Create a Gmail filter that labels your Substack mail (see README)."
            )

        since = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime("%d-%b-%Y")
        status, data = imap.search(None, "SINCE", since)
        if status != "OK":
            return []

        articles: list[Article] = []
        for num in data[0].split():
            status, msgdata = imap.fetch(num, "(RFC822)")
            if status != "OK" or not msgdata or not msgdata[0]:
                continue
            msg = email.message_from_bytes(msgdata[0][1], policy=default_policy)

            uid = str(msg["message-id"] or "").strip()
            if not uid or uid in seen:
                continue

            html = _body_html(msg)
            url = _extract_post_url(html)
            text = _strip_html(html)
            if len(text) < MIN_ARTICLE_CHARS or not url:
                # Too short or no post link => likely a notification/system email, not a post.
                seen.add(uid)
                continue

            from_hdr = msg["from"]
            author = "Substack"
            if from_hdr is not None and from_hdr.addresses:
                addr = from_hdr.addresses[0]
                author = addr.display_name or addr.addr_spec

            when = "unknown date"
            date_hdr = msg["date"]
            if date_hdr is not None and getattr(date_hdr, "datetime", None):
                when = date_hdr.datetime.strftime("%Y-%m-%d")

            articles.append(Article(
                id=uid,
                title=str(msg["subject"] or "(no subject)"),
                author=author,
                url=url,
                feed=author,
                published=when,
                text=text,
            ))

        return articles
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 — logout best-effort
            pass
