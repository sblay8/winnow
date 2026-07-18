# Claude Content Agent

Pulls new Substack posts — from your Gmail inbox by default — uses a Claude agent
(built on Google's Agent Development Kit) to decide which are genuinely useful,
summarizes the good ones, and emails you a digest.

```
Substack posts  ─▶  fetch new posts  ─▶  ADK + Claude agent  ─▶  useful?  ─▶  digest email
(Gmail or RSS)      (gmail/feed_reader)   (agent.py)             yes │
                                                                    └▶ summary + key points
```

## Where posts come from (`SOURCE` in config.py)

- **`"gmail"` (default)** — reads Substack posts straight from your Gmail. Whatever
  you subscribe to on Substack lands in your inbox and flows in automatically —
  there's no feed list to maintain. Requires a one-time Gmail filter (below).
- **`"rss"`** — reads the explicit `FEEDS` list in `config.py` instead.

### One-time Gmail filter (for `"gmail"` mode)

Tell Gmail to label your Substack mail so the app knows what to read:

1. Gmail → search bar dropdown → **Create filter**.
2. In **From**, put: `substack.com OR substackmail.com`
3. **Create filter** → check **Apply the label** → choose/create label **`Substack`**
   (must match `GMAIL_LABEL` in `config.py`). Optionally tick "Also apply to matching
   conversations" to backfill existing mail.

Reading uses IMAP with the *same* `GMAIL_APP_PASSWORD` used for sending — no extra setup.

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

## Use your Obsidian vault as context (optional)

The agent can weigh incoming articles against what's already in your notes — favoring
things that **deepen active interests** or **fill gaps** your vault implies, and downranking
what you already know cold.

1. Set `VAULT_PATH` in `.env` to your vault folder (local only; never committed).
2. Build the profile (runs locally, reads your notes, distills them via Claude):
   ```bash
   .venv/bin/python build_vault_profile.py
   ```
   This writes `vault_context.md` — a compact profile (core areas, active interests, gaps,
   tag/title index). **Only this distillation** is written; your raw notes never leave your machine
   beyond that one Claude call.
3. Commit `vault_context.md` so the hosted job uses it:
   ```bash
   git add vault_context.md && git commit -m "Update vault profile" && git push
   ```

When the file is present, each pick shows a **"Relates to your vault"** line and a **"Fills a gap"**
badge where relevant. Re-run the build script whenever your vault changes meaningfully. Delete
`vault_context.md` to turn the feature off.

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
| `config.py` | Source, interests, thresholds, feeds — **edit this** |
| `gmail_reader.py` | Reads Substack posts from your Gmail via IMAP (default source) |
| `feed_reader.py` | Fetches + cleans RSS articles (when `SOURCE = "rss"`) |
| `agent.py` | ADK `LlmAgent` on Claude; returns a structured useful/summary verdict (vault-aware) |
| `build_vault_profile.py` | Distills your Obsidian vault into `vault_context.md` (run locally) |
| `emailer.py` | Renders + sends the Gmail digest |
| `state.py` | `seen.json` dedup so nothing repeats |
| `main.py` | Orchestrates fetch → analyze → email |
