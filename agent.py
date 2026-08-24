"""The content-analyst agent: Claude (via ADK + LiteLlm) judges usefulness and summarizes."""
import json
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from config import CLAUDE_MODEL, INTERESTS, VAULT_CONTEXT_FILE

APP_NAME = "winnow"
USER_ID = "local"


class Analysis(BaseModel):
    """Structured verdict the agent must return for each article."""
    is_useful: bool = Field(description="True only if this is worth the reader's time given their interests.")
    relevance: int = Field(ge=1, le=10, description="1 = irrelevant/low-value, 10 = must-read for this reader.")
    reason: str = Field(description="One sentence: why it is or isn't useful to this reader.")
    summary: str = Field(default="", description="If useful: 2-4 sentence plain-language summary. Else empty string.")
    key_points: list[str] = Field(default_factory=list, description="If useful: 2-5 concrete takeaways. Else empty.")
    tags: list[str] = Field(default_factory=list, description="1-4 short topic tags, e.g. 'AI', 'economics'.")
    relation_to_vault: str = Field(default="", description="If it connects to the reader's notes, one phrase on how; else ''.")
    fills_gap: bool = Field(default=False, description="True if it addresses a gap/thin area in the reader's vault.")
    gap_area: str = Field(default="", description="If fills_gap, the vault area it fills; else ''.")


def _load_vault_context() -> str:
    if os.path.exists(VAULT_CONTEXT_FILE):
        with open(VAULT_CONTEXT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


VAULT_CONTEXT = _load_vault_context()

# Injected only when a vault profile has been built; otherwise the agent behaves as before.
VAULT_BLOCK = (f"""

The reader keeps a knowledge vault (their own notes). Weigh articles against it:
- FAVOR articles that deepen their active/emerging interests, or that FILL a gap the vault implies
  (set fills_gap=true and name the area in gap_area).
- DOWNRANK articles that merely rehash what they already know deeply (redundant → lower relevance).
- When an article connects to their notes, say how in relation_to_vault.

VAULT PROFILE:
{VAULT_CONTEXT}
""" if VAULT_CONTEXT else "")


INSTRUCTION = f"""You are a discerning reading assistant. You are helping deal with the influx of content and deciding what is useful and guiding the reader to what is worth the time to consume.
You will be given the full text of an article and must determine if there are useful insights within. Be wary of content marketing and rhetoric and salesly content. You are critical of any content
are wary of verbose, or overly emotional or misleading content. Beware of biases that the content creator is employing. 

The reader's interests:
{INTERESTS}

Judge on substance, not topic keywords: reward original analysis, concrete data, and actionable
insight; penalize filler, rehashed news, pure opinion with no support, and paywall teasers.
Be selective — it is better to skip a mediocre article than to waste the reader's attention.
{VAULT_BLOCK}
Respond with ONLY a single JSON object (no prose, no markdown code fences) with exactly these keys:
  "is_useful":         boolean — true only if worth the reader's time
  "relevance":         integer 1-10 — 1 irrelevant, 10 must-read (raise for gap-fillers, lower for redundant)
  "reason":            string — one sentence on why it is / isn't useful
  "summary":           string — if useful, a 2-4 sentence plain-language summary; else ""
  "key_points":        array of strings — if useful, 2-5 concrete takeaways; else []
  "tags":              array of strings — 1-4 short topic tags
  "relation_to_vault": string — if it connects to the reader's notes/areas, one phrase on how; else ""
  "fills_gap":         boolean — true if it addresses a gap/thin area in their vault
  "gap_area":          string — if fills_gap, the vault area it fills; else ""

If is_useful is false, leave summary "" and key_points []. Write the summary and key points so
the reader gets the real value without opening the article."""

# Built once and reused across all articles in a run.
# NB: we intentionally do NOT set output_schema — ADK's built-in validator mishandles the
# {"json": {...}} envelope that the LiteLlm+Anthropic path returns. We parse/validate ourselves.
_agent = LlmAgent(
    name="content_analyst",
    model=LiteLlm(model=CLAUDE_MODEL),
    instruction=INSTRUCTION,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
_session_service = InMemorySessionService()
_runner = Runner(agent=_agent, app_name=APP_NAME, session_service=_session_service)


async def analyze_article(article, index: int) -> Analysis:
    """Run the agent on one article and return its structured Analysis."""
    session_id = f"article-{index}"
    await _session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    prompt = (
        f"TITLE: {article.title}\n"
        f"AUTHOR: {article.author}\n"
        f"SOURCE: {article.feed}\n\n"
        f"ARTICLE TEXT:\n{article.text[:20000]}"
    )
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    raw = None
    async for event in _runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            # Claude may prepend thinking blocks (empty .text); join all real text parts.
            texts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if texts:
                raw = "\n".join(texts)

    if not raw:
        raise RuntimeError("Agent returned no response")
    return _parse_analysis(raw)


def _parse_analysis(raw: str) -> Analysis:
    """Extract, unwrap, and validate the JSON verdict from the model's raw text."""
    text = raw.strip()
    # Strip ```json ... ``` fences if the model added them.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    # Fall back to slicing the outermost { ... } if there's stray prose.
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object in response: {raw[:200]!r}")
        text = text[start:end + 1]

    data = json.loads(text)
    # LiteLlm+Anthropic sometimes wraps the payload as {"json": {...}}.
    if isinstance(data, dict) and set(data.keys()) == {"json"}:
        data = data["json"]
    return Analysis(**data)
