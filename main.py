"""Entry point: fetch -> analyze -> email. Run with `python main.py` (or `--dry-run`)."""
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from config import MIN_RELEVANCE, SOURCE
from state import load_seen, save_seen

if SOURCE == "gmail":
    from gmail_reader import fetch_new_articles
else:
    from feed_reader import fetch_new_articles


async def run(dry_run: bool) -> int:
    # Import here so a missing ANTHROPIC_API_KEY fails with a clear message, not on import.
    from agent import analyze_article
    from emailer import send_digest

    seen = load_seen()
    print(f"Reading new articles from {SOURCE}…")
    try:
        articles = fetch_new_articles(seen)
    except RuntimeError as e:
        sys.exit(f"Could not read articles: {e}")
    if not articles:
        print("No new articles. Nothing to do.")
        save_seen(seen)  # persist any teasers marked seen during fetch
        return 0

    print(f"Found {len(articles)} new article(s). Analyzing with Claude…\n")
    picks: list[dict] = []
    skipped: list[dict] = []
    for i, article in enumerate(articles):
        try:
            analysis = await analyze_article(article, i)
        except Exception as e:  # noqa: BLE001 — one bad article shouldn't kill the run
            print(f"  ✗ error on “{article.title}”: {e} (will retry next run)")
            continue

        seen.add(article.id)
        useful = analysis.is_useful and analysis.relevance >= MIN_RELEVANCE
        mark = "✓ keep" if useful else "· skip"
        print(f"  {mark}  [{analysis.relevance}/10] {article.title} — {analysis.reason}")
        (picks if useful else skipped).append({"article": article, "analysis": analysis})

    save_seen(seen)
    print(f"\n{len(picks)} passed the bar (>= {MIN_RELEVANCE}/10), {len(skipped)} skipped.")
    if not picks and not skipped:
        print("Nothing analyzed this run — no email.")
        return 0

    if dry_run:
        os.makedirs("out", exist_ok=True)
        from emailer import _render_html
        path = os.path.join("out", "digest.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_render_html(picks, skipped))
        print(f"Dry run — wrote preview to {path} (no email sent).")
    else:
        send_digest(picks, skipped)
        print(f"Sent digest to {os.environ.get('DIGEST_TO') or os.environ.get('GMAIL_ADDRESS')}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Substack -> Claude -> email content pipeline.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze and write an HTML preview to out/ instead of sending email.")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
    if SOURCE == "gmail" and not (os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD")):
        sys.exit("SOURCE is 'gmail' but GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not set in .env.")

    sys.exit(asyncio.run(run(args.dry_run)))


if __name__ == "__main__":
    main()
