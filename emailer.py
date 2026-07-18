"""Builds and sends the digest email via Gmail SMTP."""
import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from html import escape


def _pick_card(it: dict) -> str:
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
    gap_badge = (
        f'<span style="background:#e7f7ec;color:#1a7f45;border-radius:4px;padding:1px 6px;'
        f'font-size:12px;">Fills a gap{": " + escape(getattr(an, "gap_area", "")) if getattr(an, "gap_area", "") else ""}</span>'
        if getattr(an, "fills_gap", False) else ""
    )
    relation = getattr(an, "relation_to_vault", "")
    relation_html = (
        f'<div style="margin-top:8px;font-size:13px;color:#666;">'
        f'<b>Relates to your vault:</b> {escape(relation)}</div>'
        if relation else ""
    )
    return f"""
        <div style="margin:0 0 26px;padding-bottom:22px;border-bottom:1px solid #eee;">
          <div style="font-size:12px;color:#888;">{escape(a.feed)} · {escape(a.published)} · relevance {an.relevance}/10</div>
          <h2 style="margin:4px 0 8px;font-size:18px;">{title_html}</h2>
          <p style="margin:0 0 10px;color:#333;line-height:1.5;">{escape(an.summary)}</p>
          {points_html}
          {relation_html}
          <div style="margin-top:8px;">{tags} {gap_badge}</div>
          {link_html}
        </div>"""


def _skipped_row(it: dict) -> str:
    a, an = it["article"], it["analysis"]
    title_html = (
        f'<a href="{escape(a.url)}" style="color:#666;">{escape(a.title)}</a>'
        if a.url else escape(a.title)
    )
    return f"""
        <li style="margin-bottom:10px;line-height:1.4;">
          <span style="color:#444;">{title_html}</span>
          <span style="color:#aaa;"> — {escape(a.feed)} · {an.relevance}/10</span>
          <div style="color:#999;">{escape(an.reason)}</div>
        </li>"""


def _skipped_section(skipped: list[dict]) -> str:
    if not skipped:
        return ""
    rows = "".join(_skipped_row(it) for it in skipped)
    return f"""
      <div style="margin-top:32px;padding-top:16px;border-top:2px solid #eee;">
        <h3 style="font-size:14px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin:0 0 12px;">
          Skipped ({len(skipped)})</h3>
        <ul style="list-style:none;padding:0;margin:0;font-size:13px;">{rows}</ul>
      </div>"""


def _render_html(picks: list[dict], skipped: list[dict] | None = None) -> str:
    skipped = skipped or []
    cards = "".join(_pick_card(it) for it in picks)
    if picks:
        header = f"{len(picks)} article{'s' if len(picks) != 1 else ''} worth your time."
    else:
        header = "Nothing cleared the bar this time — see what was reviewed below."
    return f"""<html><body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      max-width:640px;margin:0 auto;padding:20px;color:#1a1a1a;">
      <h1 style="font-size:22px;margin:0 0 4px;">Your content digest</h1>
      <p style="color:#888;margin:0 0 24px;font-size:13px;">{header}</p>
      {cards}
      {_skipped_section(skipped)}
      <p style="color:#aaa;font-size:12px;margin-top:20px;">Curated by your Claude content agent.</p>
    </body></html>"""


def _render_text(picks: list[dict], skipped: list[dict] | None = None) -> str:
    skipped = skipped or []
    if picks:
        lines = [f"Your content digest — {len(picks)} article(s) worth your time.\n"]
    else:
        lines = ["Your content digest — nothing cleared the bar this time.\n"]
    for it in picks:
        a, an = it["article"], it["analysis"]
        lines.append(f"## {a.title}  ({a.feed}, {a.published}, relevance {an.relevance}/10)")
        lines.append(an.summary)
        for p in an.key_points:
            lines.append(f"  - {p}")
        if getattr(an, "fills_gap", False):
            lines.append(f"  [Fills a gap: {an.gap_area}]" if an.gap_area else "  [Fills a gap]")
        if getattr(an, "relation_to_vault", ""):
            lines.append(f"  Relates to your vault: {an.relation_to_vault}")
        if a.url:
            lines.append(f"  {a.url}")
        lines.append("")
    if skipped:
        lines.append(f"\n--- Skipped ({len(skipped)}) ---")
        for it in skipped:
            a, an = it["article"], it["analysis"]
            lines.append(f"- {a.title} ({a.feed}, {an.relevance}/10): {an.reason}")
    return "\n".join(lines)


def send_digest(picks: list[dict], skipped: list[dict] | None = None) -> None:
    """Send the digest. Raises if Gmail credentials are missing."""
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("DIGEST_TO") or sender
    if not sender or not password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    n = len(picks)
    msg = EmailMessage()
    msg["Subject"] = f"Content digest — {n} pick{'s' if n != 1 else ''}"
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(_render_text(picks, skipped))
    msg.add_alternative(_render_html(picks, skipped), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password.replace(" ", ""))
        server.send_message(msg)
