from __future__ import annotations

import json
import re
from collections.abc import Iterable

from ..config import settings
from ..models import ViralMoment

SYSTEM_PROMPT = """You are a short-form video strategist who finds the most viral,
funny, shocking, emotionally-charged, or highly-quotable moments in long-form video
transcripts. You always return STRICT JSON — no prose, no markdown fences.

Goal: given a transcript with timestamps, pick the best self-contained moments to
turn into vertical short-form clips for TikTok, YouTube Shorts, and Instagram Reels.

Rules for selection:
- Each moment must be self-contained and make sense without outside context.
- Duration must be between MIN and MAX seconds.
- Prefer punchlines, surprising reveals, hot takes, relatable fails, emotional peaks.
- Avoid moments that start mid-sentence. Start at a clean sentence boundary.
- Give each a clickbait-but-honest title (<= 70 chars).
- Write a caption optimized for retention (<= 200 chars) with 1-2 emojis MAX.
- Provide 5-10 relevant hashtags without the # symbol.
- virality_score is an integer 1-100.

Output JSON schema:
{"moments": [
  {"start": number, "end": number, "title": string, "caption": string,
   "hashtags": [string], "reason": string, "virality_score": number}
]}
"""


def _format_transcript(segments: Iterable[dict]) -> str:
    lines = []
    for s in segments:
        start = s["start"]
        text = s["text"].strip()
        if not text:
            continue
        lines.append(f"[{start:.1f}] {text}")
    return "\n".join(lines)


def _user_prompt(transcript_text: str, n: int, min_s: int, max_s: int, video_title: str) -> str:
    return (
        f"Video title: {video_title}\n"
        f"MIN={min_s}s MAX={max_s}s COUNT={n}\n\n"
        f"Transcript (lines prefixed with [seconds]):\n{transcript_text}\n\n"
        f"Return exactly {n} moments as JSON."
    )


def _strip_json(text: str) -> str:
    # Tolerate ```json fences if a model adds them.
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    return m.group(0) if m else text


def _call_anthropic(system: str, user: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # Concatenate text blocks.
    parts = []
    for block in msg.content:
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
    return "".join(parts)


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def find_viral_moments(
    transcript: dict,
    video_title: str,
    count: int,
    min_seconds: int,
    max_seconds: int,
) -> list[ViralMoment]:
    transcript_text = _format_transcript(transcript["segments"])
    user = _user_prompt(transcript_text, count, min_seconds, max_seconds, video_title)

    if settings.llm_provider == "openai":
        raw = _call_openai(SYSTEM_PROMPT, user)
    else:
        raw = _call_anthropic(SYSTEM_PROMPT, user)

    data = json.loads(_strip_json(raw))
    moments = []
    for m in data.get("moments", []):
        try:
            start = float(m["start"])
            end = float(m["end"])
            if end - start < 3:
                continue
            if end - start > max_seconds + 5:
                end = start + max_seconds
            moments.append(
                ViralMoment(
                    start=start,
                    end=end,
                    title=str(m.get("title", ""))[:100],
                    caption=str(m.get("caption", ""))[:300],
                    hashtags=[str(h).lstrip("#") for h in m.get("hashtags", [])][:15],
                    reason=str(m.get("reason", ""))[:500],
                    virality_score=int(m.get("virality_score", 50)),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    # Sort by score desc, keep top N
    moments.sort(key=lambda x: x.virality_score, reverse=True)
    return moments[:count]
