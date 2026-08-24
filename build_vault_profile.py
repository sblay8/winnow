"""Distill your Obsidian vault into a compact `vault_context.md` the agent can use.

Runs LOCALLY (reads your vault from VAULT_PATH). Only the derived profile is written
out and committed — your raw notes never leave your machine beyond the Claude call
that distills them. Re-run whenever your vault has changed meaningfully:

    .venv/bin/python build_vault_profile.py
"""
import os
import re
import sys
from collections import Counter

import litellm
from dotenv import load_dotenv

load_dotenv()

from config import CLAUDE_MODEL, VAULT_CONTEXT_FILE

# Per-note excerpt + overall corpus budget keep us safely inside the model's context.
EXCERPT_CHARS = 2500
MAX_CORPUS_CHARS = 600_000

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_INLINE_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_][A-Za-z0-9_/\-]*)")

PROFILE_PROMPT = """You are building a knowledge profile of a person from their personal notes
(an Obsidian vault). A downstream agent will use this profile to decide which incoming articles
are worth their attention. Produce a CONCISE markdown profile with EXACTLY these sections:

## Core areas of expertise
Topics they clearly know deeply (detailed, repeated notes). Articles rehashing these are redundant.

## Active / emerging interests
Topics they are actively developing but where coverage is still thin or in progress. Articles that
deepen these are high value.

## Gaps and open questions
Adjacent topics their notes point toward or imply but do NOT yet cover — where new material would
fill a hole. Be specific and concrete.

## Themes and vocabulary
Recurring concepts, frameworks, and terms they use, so the agent recognizes relevant material.

Keep it under ~600 words. Be concrete and specific to THIS person — no generic filler.

Here are their notes (title, tags, excerpt each):

"""


def _read_note(path: str) -> tuple[str, list[str], str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    body = raw
    tags: list[str] = []
    fm = _FRONTMATTER_RE.match(raw)
    if fm:
        block = fm.group(1)
        body = raw[fm.end():]
        m = re.search(r"(?m)^tags:\s*(.*)$", block)
        if m:
            tags += re.findall(r"[A-Za-z0-9_][A-Za-z0-9_/\-]*", m.group(1))
    tags += _INLINE_TAG_RE.findall(body)
    tags = [t for t in tags if _is_real_tag(t)]
    title = os.path.splitext(os.path.basename(path))[0]
    return title, sorted(set(tags)), body.strip()


def _is_real_tag(t: str) -> bool:
    """Drop false positives: bare numbers and hex colors (e.g. #F6F6F6) aren't tags."""
    if t.isdigit() or re.fullmatch(r"[0-9A-Fa-f]{3,8}", t):
        return False
    return any(c.isalpha() for c in t)


def gather_notes(vault: str) -> list[tuple[str, list[str], str]]:
    notes = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in (".obsidian", ".trash", "__pycache__")]
        for name in files:
            if name.endswith(".md"):
                notes.append(_read_note(os.path.join(root, name)))
    return sorted(notes, key=lambda n: n[0].lower())


def build_corpus(notes) -> tuple[str, int]:
    """Title+tags for every note; excerpts until the char budget is spent."""
    parts, used, with_excerpt = [], 0, 0
    for title, tags, body in notes:
        tagstr = f" [tags: {', '.join(tags)}]" if tags else ""
        if used < MAX_CORPUS_CHARS:
            excerpt = body[:EXCERPT_CHARS]
            used += len(excerpt)
            with_excerpt += 1
            parts.append(f"## {title}{tagstr}\n{excerpt}\n")
        else:
            parts.append(f"## {title}{tagstr}\n(excerpt omitted — corpus budget reached)\n")
    return "\n".join(parts), with_excerpt


def build_index(notes) -> str:
    tag_counts = Counter(t for _, tags, _ in notes for t in tags)
    top_tags = ", ".join(f"{t} ({c})" for t, c in tag_counts.most_common(40)) or "—"
    titles = "\n".join(f"- {title}" for title, _, _ in notes)
    return f"## Tag index (most used)\n{top_tags}\n\n## All note titles ({len(notes)})\n{titles}\n"


def main() -> None:
    vault = os.environ.get("VAULT_PATH")
    if not vault or not os.path.isdir(vault):
        sys.exit(f"VAULT_PATH is not set to a valid directory (got: {vault!r}). Add it to .env.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")

    notes = gather_notes(vault)
    if not notes:
        sys.exit(f"No .md notes found under {vault}.")
    print(f"Read {len(notes)} notes from {vault}.")

    corpus, with_excerpt = build_corpus(notes)
    if with_excerpt < len(notes):
        print(f"  note: corpus budget reached — {with_excerpt}/{len(notes)} notes included with excerpts, "
              f"the rest by title+tags only.")

    print(f"Distilling profile with {CLAUDE_MODEL}…")
    resp = litellm.completion(
        model=CLAUDE_MODEL,
        messages=[{"role": "user", "content": PROFILE_PROMPT + corpus}],
        max_tokens=4000,
    )
    profile = resp.choices[0].message.content.strip()

    output = (
        f"# Vault knowledge profile\n\n"
        f"_Auto-generated from {len(notes)} notes by build_vault_profile.py. "
        f"Do not edit by hand — re-run the script instead._\n\n"
        f"{profile}\n\n---\n\n{build_index(notes)}"
    )
    with open(VAULT_CONTEXT_FILE, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Wrote {VAULT_CONTEXT_FILE} ({len(output)} chars).")
    print("It is gitignored on purpose. To let the hosted job use it, upload it as a secret:")
    print("  gh secret set VAULT_CONTEXT < vault_context.md")


if __name__ == "__main__":
    main()
