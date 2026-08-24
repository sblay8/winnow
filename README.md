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
git clone https://github.com/sblay8/claude-content-agent.git
cd claude-content-agent
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
3. To let the hosted job use it, store it as a **repository secret** — `vault_context.md`
   is gitignored on purpose, since the profile describes your notes, interests and
   knowledge gaps:
   ```bash
   gh secret set VAULT_CONTEXT < vault_context.md
   ```
   Re-run this whenever you rebuild the profile. With the secret unset the agent
   simply runs without vault context. See `vault_context.example.md` for the format.

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

## Scheduling and state

The digest runs daily on GitHub Actions (`.github/workflows/digest.yml`) at 05:23 UTC.
The odd minute is deliberate: GitHub runs scheduled jobs on a *best-effort* basis and
top-of-hour slots queue behind everyone else's — at 06:30 UTC this job was landing
36–171 minutes late.

Runs are stateful, so a scheduled run only summarizes genuinely new posts. State
does **not** live in git — committing `seen.json` on every run buried the project
history under dozens of bot commits, and runtime state doesn't belong in source
control anyway. Instead:

- `seen.json` round-trips through the **Actions cache** (rolling key + `restore-keys`).
- `seen.seed.json` is a committed bootstrap snapshot, read only when no cache exists.
  Without it a cold start would re-analyze `MAX_AGE_DAYS` of backlog in one go.

The job therefore needs only `contents: read`.

To run it on your own machine instead:

```cron
23 5 * * *  cd /path/to/claude-content-agent && .venv/bin/python main.py >> cron.log 2>&1
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
| `state.py` | Dedup state (Actions cache, with `seen.seed.json` fallback) |
| `main.py` | Orchestrates fetch → analyze → email |

Not committed: `.env` (secrets) and `vault_context.md` (personal knowledge profile).
