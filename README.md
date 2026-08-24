# Claude Content Agent

**A personalized reading filter.** It reads the Substack newsletters piling up in your
inbox, uses a Claude agent to judge which ones are actually worth your time — weighted
against a profile of your own notes — and emails you a short digest of the survivors.

[![Content digest](https://github.com/sblay8/claude-content-agent/actions/workflows/digest.yml/badge.svg)](https://github.com/sblay8/claude-content-agent/actions/workflows/digest.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)

The problem it solves isn't summarization — plenty of tools do that. It's **triage**.
Subscribing to good writers still leaves you with more than you can read, and the
limiting factor is deciding what to skip. This agent makes that call, explains its
reasoning, and is deliberately biased toward skipping.

## What it actually produces

Real output from a scheduled run:

```
Reading new articles from gmail…
Found 3 new article(s). Analyzing with Claude…

  · skip  [2/10] From AI Adoption to Transformation, Part III
          — Vague, image-dependent musings on AI transformation with no concrete
            frameworks, data, or actionable detail beyond buzzword-y figure captions.
  · skip  [1/10] We’ve never seen an Anthropic before
          — Speculative, hype-driven financial commentary with unverifiable/fabricated
            figures and no actionable insight for AI practitioners, ending in a subscription paywall pitch.
  ✓ keep  [7/10] Building AI-Readiness: The Seven Stages of Data Platform Architecture
          — Presents a structured seven-stage maturity model linking data platform
            architecture directly to AI/agent readiness, offering a coherent
            sequencing argument rather than just buzzwords.

1 passed the bar (>= 6/10), 2 skipped.
Sent digest to ***.
```

Two of three dropped, each with a reason. The kept article gets a summary, key
takeaways, and — where relevant — a note on how it connects to the reader's existing
notes.

<!-- TODO: add a screenshot of a rendered digest email here, e.g.:
     ![Digest email](docs/digest-screenshot.png)
     Generate one with `python main.py --dry-run` and open out/digest.html -->

## How it works

```
Substack emails          ┌───────────────────────────┐
(Gmail label, IMAP)  ──▶ │  fetch new + dedup        │  seen state (Actions cache)
   or RSS feeds          │  gmail_reader / feed_reader│
                         └────────────┬──────────────┘
                                      ▼
                         ┌───────────────────────────┐
    vault profile   ──▶  │  ADK LlmAgent on Claude   │  structured verdict:
    (repo secret)        │  agent.py                 │  is_useful, relevance 1-10,
                         └────────────┬──────────────┘  summary, key_points, gap flags
                                      ▼
                              relevance >= 6 ?
                                 │        │
                              yes│        │no
                                 ▼        ▼
                         ┌───────────────────────────┐
                         │  HTML digest email        │  picks + a "skipped" list
                         │  emailer.py               │  so nothing vanishes silently
                         └───────────────────────────┘
```

Runs daily on GitHub Actions. No server, no database.

## Design decisions

The parts that took actual thought, and what they cost:

**Relevance is novelty-weighted, not keyword-matched.** A topic filter would surface
the same ground repeatedly. Instead, `build_vault_profile.py` distills an Obsidian
vault into a profile of core expertise, active interests, and *gaps*. The agent then
favors articles that fill a gap, and **downranks articles that rehash what the reader
already knows cold**. Relevance becomes a function of the reader's current knowledge
rather than the article alone.

**The inbox is the subscription list.** Reading Substack mail over IMAP means there's
no feed list to maintain — subscribe to something and it flows in automatically. The
tradeoff is a one-time Gmail filter and parsing email HTML rather than clean RSS.

**Model output is treated as untrusted input.** `_parse_analysis` handles markdown
fences, stray prose around the JSON, and a `{"json": {...}}` envelope that the
LiteLLM→Anthropic path sometimes returns, before Pydantic validation. ADK's built-in
`output_schema` validator mishandles that envelope, so parsing is done explicitly.

**One bad article can't kill the run.** Analysis failures are caught per-article and
the item is left unmarked, so it retries on the next run instead of being silently
dropped or blocking the digest.

**Personal data stays out of the repo.** The vault profile describes its owner's
interests and knowledge gaps, so it's gitignored and injected from a repository
secret at runtime. An absent secret degrades cleanly to no-vault-context.

**Runtime state stays out of git.** Dedup state round-trips through the Actions cache
rather than being committed each run — which had buried the project history under
bot commits. A committed seed snapshot handles cold starts, so a cache miss can't
trigger a full-backlog re-analysis. The job needs only `contents: read`.

**Scheduled at 05:23 UTC, not 06:30.** GitHub runs scheduled workflows on a
best-effort basis and on-the-hour slots queue behind everyone else's. At 06:30 this
job landed 36–171 minutes late; an odd minute plus a deliberate buffer fixed it.

**Google ADK is more framework than this single-turn call needs.** It was chosen as
scaffolding for planned multi-agent work — story clustering, a groundedness critic,
tool-based fact-checking — none of which exists yet. As it stands the agent is
stateless and tool-less, so the abstraction is not yet earning its keep. Documented
here rather than hidden, because it's a real tradeoff.

## Known limitations

- **No eval suite.** Judgment quality is assessed by reading the output, not measured.
  A labelled set with precision/recall per model is the most valuable next addition.
- **Judges email HTML, not the article.** Body text is taken from the Substack email
  and truncated at 20k chars, so image-heavy or paywalled posts are a degraded signal.
  The canonical post URL is already extracted and could be fetched instead.
- **Articles are scored in isolation.** Several newsletters covering the same story
  produce several summaries rather than one synthesis.
- **No feedback loop.** Actual reading behaviour never informs future scoring.

## Setup

```bash
git clone https://github.com/sblay8/claude-content-agent.git
cd claude-content-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then edit
```

Fill in `.env`:

- **`ANTHROPIC_API_KEY`** — from <https://console.anthropic.com/settings/keys>
- **`GMAIL_APP_PASSWORD`** — a Google *App Password* (needs 2-Step Verification on),
  created at <https://myaccount.google.com/apppasswords>. Not your normal password.

```bash
python main.py --dry-run    # analyze + write out/digest.html, send nothing
python main.py              # analyze + email the digest
```

The first run only needs the Anthropic key; add the Gmail values before dropping
`--dry-run`.

### Choosing a source (`SOURCE` in `config.py`)

- **`"gmail"` (default)** — reads Substack posts from your Gmail. Needs a one-time
  filter: Gmail → **Create filter** → From `substack.com OR substackmail.com` →
  **Apply the label** `Substack` (must match `GMAIL_LABEL`). Reading uses IMAP with
  the *same* app password used for sending.
- **`"rss"`** — reads the explicit `FEEDS` list in `config.py` instead.

### Vault-aware ranking (optional)

1. Set `VAULT_PATH` in `.env` to your Obsidian vault.
2. Build the profile — reads your notes locally, distills them in a single Claude call:
   ```bash
   .venv/bin/python build_vault_profile.py
   ```
   Only the distillation is written to `vault_context.md`; raw notes never leave your
   machine beyond that one call.
3. To let the hosted job use it, upload it as a secret (the file is gitignored
   deliberately — it describes your interests and knowledge gaps):
   ```bash
   gh secret set VAULT_CONTEXT < vault_context.md
   ```

Each pick then shows a **"Relates to your vault"** line and a **"Fills a gap"** badge
where relevant. See `vault_context.example.md` for the format. Delete the file and
unset the secret to turn the feature off.

### Other settings (`config.py`)

| Setting | Effect |
|---|---|
| `INTERESTS` | Plain-English description of what "useful" means — steers the agent |
| `MIN_RELEVANCE` | The 1–10 bar an article must clear to be emailed (default 6) |
| `CLAUDE_MODEL` | Any Anthropic model; `anthropic/claude-haiku-4-5-20251001` for a cheaper pass |
| `MAX_AGE_DAYS` | How far back to look on a cold start |
| `FEEDS` | Feeds to watch when `SOURCE = "rss"` |

To run on your own machine instead of Actions:

```cron
23 5 * * *  cd /path/to/claude-content-agent && .venv/bin/python main.py >> cron.log 2>&1
```

## Files

| File | Role |
|------|------|
| `main.py` | Orchestrates fetch → analyze → email |
| `agent.py` | ADK `LlmAgent` on Claude; returns the structured verdict |
| `gmail_reader.py` | Reads Substack posts from Gmail via IMAP (default source) |
| `feed_reader.py` | Fetches + cleans RSS articles (when `SOURCE = "rss"`) |
| `build_vault_profile.py` | Distills an Obsidian vault into `vault_context.md` (run locally) |
| `emailer.py` | Renders + sends the HTML digest |
| `state.py` | Dedup state (Actions cache, with `seen.seed.json` fallback) |
| `config.py` | Source, interests, thresholds — **the file you edit** |

Not committed: `.env` (secrets) and `vault_context.md` (personal knowledge profile).
