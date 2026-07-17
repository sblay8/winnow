"""Builds and sends the digest email via Gmail SMTP."""
import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from html import escape


def _render_html(items: list[dict]) -> str:
    """items: list of {"article": Article, "analysis": Analysis}."""
    cards = []
    for it in items:
        a, an = it["article"], it["analysis"]
        points = "".join(f"<li>{escape(p)}</li>" for p in an.key_points)
        points_html = f"<ul>{points}</ul>" if points else ""
        tags = " ".join(
            f'<span style="background:#eef;border-radius:4px;padding:1px 6px;'
            f'font-size:12px;color:#334;">{escape(t)}</span>'
            for t in an.tags
        )
        link_html = (
            f'<div style="margin-top:10px;font-size:13px;">'
            f'<a href="{escape(a.url)}" style="color:#3355dd;">Read the full article &rarr;</a></div>'
            if a.url else ""
        )
        title_html = (
            f'<a href="{escape(a.url)}" style="color:#1a1a1a;text-decoration:none;">{escape(a.title)}</a>'
            if a.url else escape(a.title)
        )
        cards.append(f"""
        <div style="margin:0 0 26px;padding-bottom:22px;border-bottom:1px solid #eee;">
          <div style="font-size:12px;color:#888;">{escape(a.feed)} · {escape(a.published)} · relevance {an.relevance}/10</div>
          <h2 style="margin:4px 0 8px;font-size:18px;">{title_html}</h2>
          <p style="margin:0 0 10px;color:#333;line-height:1.5;">{escape(an.summary)}</p>
          {points_html}
          <div style="margin-top:8px;">{tags}</div>
          {link_html}
        </div>""")

    return f"""<html><body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      max-width:640px;margin:0 auto;padding:20px;color:#1a1a1a;">
      <h1 style="font-size:22px;margin:0 0 4px;">Your content digest</h1>
      <p style="color:#888;margin:0 0 24px;font-size:13px;">
        {len(items)} article{'s' if len(items) != 1 else ''} worth your time.</p>
      {''.join(cards)}
      <p style="color:#aaa;font-size:12px;margin-top:20px;">Curated by your Claude content agent.</p>
    </body></html>"""


def _render_text(items: list[dict]) -> str:
    lines = [f"Your content digest — {len(items)} article(s) worth your time.\n"]
    for it in items:
        a, an = it["article"], it["analysis"]
        lines.append(f"## {a.title}  ({a.feed}, {a.published}, relevance {an.relevance}/10)")
        lines.append(an.summary)
        for p in an.key_points:
            lines.append(f"  - {p}")
        lines.append(f"  {a.url}\n")
    return "\n".join(lines)


def send_digest(items: list[dict]) -> None:
    """Send the digest. Raises if Gmail credentials are missing."""
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("DIGEST_TO") or sender
    if not sender or not password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    msg = EmailMessage()
    msg["Subject"] = f"Content digest — {len(items)} pick{'s' if len(items) != 1 else ''}"
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(_render_text(items))
    msg.add_alternative(_render_html(items), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password.replace(" ", ""))
        server.send_message(msg)
