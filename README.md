# Claude Content Agent

Watches Substack RSS feeds, uses a Claude agent (built on Google's Agent
Development Kit) to decide which new articles are genuinely useful, summarizes
the good ones, and emails you a digest.

```
feeds (RSS)  ─▶  fetch new posts  ─▶  ADK + Claude agent  ─▶  useful?  ─▶  digest email
                 (feed_reader)        (agent.py)              yes │
                                                                  └▶ summary + key points
```

## Setup

```bash
cd /Users/stephenblaylock/Documents/Claude/claude_content
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then edit .env (see below)
```

Fill in `.env`:

- **`ANTHROPIC_API_KEY`** — from <https://console.anthropic.com/settings/keys>
- **`GMAIL_APP_PASSWORD`** — a Google *App Password* (needs 2-Step Verification on),
  created at <https://myaccount.google.com/apppasswords>. Not your normal password.

## Run

```bash
python main.py --dry-run    # analyze + write out/digest.html, send nothing
python main.py              # analyze + email the digest
```

The first real run only needs Anthropic; add the Gmail values before dropping
`--dry-run`.

## Customize (`config.py`)

- `FEEDS` — the Substack feeds to watch (`https://<name>.substack.com/feed`).
- `INTERESTS` — plain-English description of what "useful" means to you. This is
  what steers the agent's judgment.
- `MIN_RELEVANCE` — the 1–10 bar an article must clear to be emailed.
- `CLAUDE_MODEL` — any Anthropic model, e.g. `anthropic/claude-haiku-4-5-20251001`
  for a cheaper/faster pass.

## Schedule it (cron)

Runs are stateful — `seen.json` records processed articles, so a scheduled run
only ever summarizes genuinely new posts. Example: every day at 8am.

```cron
0 8 * * *  cd /Users/stephenblaylock/Documents/Claude/claude_content && .venv/bin/python main.py >> cron.log 2>&1
```

## Files

| File | Role |
|------|------|
| `config.py` | Feeds, interests, thresholds — **edit this** |
| `feed_reader.py` | Fetches + cleans RSS articles |
| `agent.py` | ADK `LlmAgent` on Claude; returns a structured useful/summary verdict |
| `emailer.py` | Renders + sends the Gmail digest |
| `state.py` | `seen.json` dedup so nothing repeats |
| `main.py` | Orchestrates fetch → analyze → email |
