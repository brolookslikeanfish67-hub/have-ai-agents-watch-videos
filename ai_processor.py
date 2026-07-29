"""
ai_processor.py

Handles Step 3 and Step 4 of the pipeline:
  3. Package the transcript (and any frames) with the user's prompt.
  4. Send it to an LLM and return a structured response.
"""

import base64
import os
from typing import List, Optional

from .extractor import Frame, format_transcript

SYSTEM_PROMPT = (
    "You are a video analysis assistant. You are given the transcript of a "
    "YouTube video, with timestamps, and optionally a set of screenshots taken "
    "at points throughout the video. Use both to answer the user's request as "
    "accurately as possible. When referencing a moment in the video, cite the "
    "timestamp in [HH:MM:SS] or [MM:SS] format so the user can jump to it."
)


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_user_text(transcript_text: str, user_prompt: str, frame_count: int) -> str:
    parts = [f"USER REQUEST:\n{user_prompt}\n"]
    if frame_count:
        parts.append(f"({frame_count} video frame(s) are attached below.)\n")
    parts.append(f"TRANSCRIPT:\n{transcript_text}")
    return "\n".join(parts)


def _call_anthropic(text: str, frames: List[Frame], model: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    content = []
    for frame in frames:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": _image_to_base64(frame.path),
                },
            }
        )
    content.append({"type": "text", "text": text})

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_openai(text: str, frames: List[Frame], model: str) -> str:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from env

    content = [{"type": "text", "text": text}]
    for frame in frames:
        b64 = _image_to_base64(frame.path)
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )

    response = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    return response.choices[0].message.content


def analyze(
    transcript_lines,
    user_prompt: str,
    frames: Optional[List[Frame]] = None,
    provider: str = "anthropic",
    model: Optional[str] = None,
) -> str:
    """Package transcript + frames and send them to the chosen LLM provider."""
    frames = frames or []
    transcript_text = format_transcript(transcript_lines)
    user_text = _build_user_text(transcript_text, user_prompt, len(frames))

    if provider == "anthropic":
        model = model or "claude-sonnet-4-6"
        return _call_anthropic(user_text, frames, model)
    elif provider == "openai":
        model = model or "gpt-4o"
        return _call_openai(user_text, frames, model)
    else:
        raise ValueError(f"Unknown provider: {provider}")
