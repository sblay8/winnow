"""Configuration for the content pipeline. This is the file you'll edit most."""
import os

# --- Where articles come from ------------------------------------------------
# "gmail" : read Substack posts from your Gmail (see GMAIL_LABEL below). The list
#           of what you follow lives in Substack/your inbox — nothing to maintain here.
# "rss"   : read from the explicit FEEDS list below instead.
SOURCE = "gmail"

# Gmail label that your Substack mail is filed under (used when SOURCE = "gmail").
# Set up a Gmail filter to apply this label to Substack emails (see README).
GMAIL_LABEL = "Substack"

# --- Substack feeds to watch (used only when SOURCE = "rss") -----------------
# Any Substack works: https://<name>.substack.com/feed
# Custom-domain Substacks expose /feed too (e.g. https://www.oneusefulthing.org/feed).
FEEDS = [
    "https://noahpinion.substack.com/feed",
    "https://www.oneusefulthing.org/feed",
]

# --- What "useful" means to you ---------------------------------------------
# Free-text description of what you care about. The agent uses this to decide
# whether an article is worth summarizing. Be as specific as you like.
INTERESTS = """
I care about: practical uses of AI/LLMs, data product management, data architecture, how technology reshapes work and the
economy, sharp original analysis, and concrete takeaways I can act on.
I do NOT care about: routine news recaps, culture-war commentary, link roundups,
personal/housekeeping posts, or paywalled teasers with little real content.
"""

# Only articles scoring at/above this (1-10) make it into the email.
MIN_RELEVANCE = 6

# Skip articles whose extracted body is shorter than this (paywall teasers, etc.).
MIN_ARTICLE_CHARS = 400

# Don't look further back than this many days on the first run of a new feed.
MAX_AGE_DAYS = 14

# --- Model -------------------------------------------------------------------
# Overridable via CLAUDE_MODEL in .env. Format is "anthropic/<model-id>".
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "anthropic/claude-sonnet-5"

# --- Obsidian vault (optional context) --------------------------------------
# If VAULT_PATH points at your vault, run `python build_vault_profile.py` to
# distill it into vault_context.md. When that file exists, the agent uses it to
# steer relevance, avoid redundancy, and favor articles that fill vault gaps.
# VAULT_PATH lives in .env (local only) — it never gets committed.

# --- Files -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Runtime dedup state. Gitignored; restored from the Actions cache between runs.
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")
# Committed bootstrap snapshot, read only when SEEN_FILE is absent (first run, or
# after a cache eviction). Prevents a cold start from re-analyzing MAX_AGE_DAYS of
# backlog and sending one enormous digest.
SEEN_SEED_FILE = os.path.join(BASE_DIR, "seen.seed.json")
VAULT_CONTEXT_FILE = os.path.join(BASE_DIR, "vault_context.md")
