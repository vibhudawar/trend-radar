"""LLM tasks (OpenAI) with Pydantic structured outputs — the RESPONSE SHAPE is guaranteed
(fields, types, enum values); wording still varies run-to-run (expected). Per-task model from config."""
from __future__ import annotations

from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel

from .config import MODEL_INTENT, MODEL_REASON, MODEL_VISION, OPENAI_API_KEY, require

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=require("OPENAI_API_KEY", OPENAI_API_KEY))
    return _client


HookType = Literal["question", "POV", "bold-claim", "curiosity-gap", "negativity",
                   "listicle", "story", "transformation", "other"]
FormatType = Literal["talking-head", "before-after", "screen-record", "text-on-video",
                     "voiceover-broll", "skit", "other"]


class IntentItem(BaseModel):
    idx: int
    is_pitch: bool


class IntentResult(BaseModel):
    items: list[IntentItem]


class OnscreenResult(BaseModel):
    onscreen_text: str
    format: FormatType


class HookResult(BaseModel):
    hook_text: str
    hook_type: HookType
    hook_source: Literal["onscreen", "spoken", "caption"]
    emotional_driver: str
    format: FormatType
    structure: str
    replication_score: int


class ConceptItem(BaseModel):
    name: str
    pattern: str
    member_idxs: list[int]


class ConceptList(BaseModel):
    concepts: list[ConceptItem]


class Beat(BaseModel):
    t: str
    action: str


class AdaptResult(BaseModel):
    adapted_hook: str
    format: FormatType
    length_s: int
    test_target: str
    script: list[Beat]


def _parse(model: str, content: Any, schema: type[BaseModel]) -> BaseModel:
    resp = client().beta.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": content}],
        response_format=schema,
    )
    parsed = resp.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError(f"{schema.__name__} parse returned no content")
    return parsed


def classify_intent(items: list[dict[str, Any]]) -> dict[int, bool]:
    listing = "\n".join(f'{i}: {it["caption"][:160]}' for i, it in enumerate(items))
    prompt = (
        "Classify short videos by MARKETING INTENT for a tool that finds reference ads for a SaaS/product. "
        "is_pitch=true if it PROMOTES a specific app/tool/software/service the viewer should use or buy; "
        "false if generic education, storytime, or entertainment. Return one item per input index.\n\n" + listing
    )
    res = _parse(MODEL_INTENT, prompt, IntentResult)
    return {it.idx: it.is_pitch for it in res.items}  # type: ignore[attr-defined]


def read_onscreen(frames_b64: list[str]) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text":
        "First seconds of a short video ad. Give the FULL on-screen overlaid text verbatim (the hook) "
        "and the visual format."}]
    for b in frames_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
    return _parse(MODEL_VISION, content, OnscreenResult).model_dump()


def extract_hook(onscreen: str, spoken: str, caption: str) -> dict[str, Any]:
    prompt = f"""Identify the REAL opening hook of a short video ad. The hook is the on-screen text or the
spoken opening — NOT the caption (caption is context only). replication_score is 0-100.

ON-SCREEN: {onscreen or '(none)'}
SPOKEN: {spoken or '(none)'}
CAPTION: {caption}"""
    return _parse(MODEL_REASON, prompt, HookResult).model_dump()


def cluster_concepts(outliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import json
    payload = [{"i": i, "hook": o.get("hook_text") or o.get("caption", "")[:160],
                "format": o.get("format")} for i, o in enumerate(outliers)]
    prompt = (
        "Group these winning short-video ads into 2-4 RECURRING CONCEPTS (repeatable hook+angle patterns). "
        "Every item maps to exactly one concept via member_idxs (0-based input indices).\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    res = _parse(MODEL_REASON, prompt, ConceptList)
    return [c.model_dump() for c in res.concepts]  # type: ignore[attr-defined]


def adapt_concept(concept: dict[str, Any], examples: list[dict[str, Any]], client_desc: str) -> dict[str, Any]:
    ex = "\n".join(f'- "{(e.get("hook_text") or e.get("caption","")[:80])}" ({e.get("view_count"):,} views)'
                   for e in examples[:4])
    prompt = f"""Concept: {concept['name']} — {concept.get('pattern','')}
Winning examples:
{ex}

CLIENT: {client_desc}

Rewrite this concept's hook for the client (punchy, <=14 words), pick format + length_s, a measurable
test_target, and a shoot-ready script of 3-4 timecoded beats."""
    return _parse(MODEL_REASON, prompt, AdaptResult).model_dump()
