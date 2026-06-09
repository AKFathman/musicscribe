"""Mode 2 generation: write the user's prompt in a classified tone.

Takes a writing prompt plus the tone a song was classified into, and produces prose
that embodies that vibe. Exposes a streaming generator (`stream_in_tone`) used by
both the CLI and the web app, plus a convenience collector (`write_in_tone`).
Streaming keeps the UI responsive and avoids HTTP timeouts on longer outputs.
"""

from typing import Callable, Iterator

from .classifier import ToneClassification
from .tones import TONE_DESCRIPTIONS


# Stable system prefix (cacheable). The specific tone + prompt go in the user turn.
_SYSTEM = (
    "You are Vibe Writer. You are given a WRITING TASK and a TARGET TONE, and you carry "
    "out the task — exactly as asked — written in that tone.\n\n"
    "Keep the two roles separate:\n"
    "- The TASK is WHAT to write: its subject, format, and intent (e.g. a LinkedIn post "
    "about a product, a poem about love, a breakup text, a cover letter). Fulfill it "
    "literally and completely — the right topic, the right format, the right audience.\n"
    "- The TONE is HOW it should feel. Apply it as a stylistic lens only — through word "
    "choice, rhythm, imagery, and pacing.\n\n"
    "The tone colors the task; it never replaces it. A melancholic LinkedIn post is still "
    "a LinkedIn post about its stated subject. A euphoric poem about love is still about "
    "love. Do NOT write about the song the tone came from, and do not drift onto the "
    "tone's stock themes instead of the task's actual subject.\n\n"
    "Guidelines:\n"
    "- Do exactly what the task asks; honor its subject and its format.\n"
    "- Convey the tone by showing it, not by naming the emotion.\n"
    "- Match length and structure to what the format implies.\n"
    "- Return only the finished piece — no preface, no explanation."
)


def _tone_brief(classification: ToneClassification) -> str:
    tone = classification.primary_tone
    parts = [f"{tone.value} — {TONE_DESCRIPTIONS[tone]}"]
    if classification.secondary_tone is not None:
        sec = classification.secondary_tone
        parts.append(f"with an undercurrent of {sec.value} ({TONE_DESCRIPTIONS[sec]})")
    brief = "; ".join(parts)
    if classification.descriptors:
        brief += f"\nSpecific texture to capture: {', '.join(classification.descriptors)}."
    return brief


def _build_user(prompt: str, classification: ToneClassification, song_title: str, song_artist: str) -> str:
    # The song is only the *source* of the tone (already captured in `classification`).
    # We deliberately do NOT name the song here — mentioning it pulls the model toward
    # writing *about the song* instead of doing the task. (song_title/song_artist are
    # kept in the signature for API compatibility but intentionally unused.)
    return (
        "WRITING TASK — do exactly this, rendered in the tone below:\n"
        f"{prompt.strip()}\n\n"
        f"TARGET TONE (style only, not the subject): {_tone_brief(classification)}"
    )


def stream_in_tone(
    prompt: str,
    classification: ToneClassification,
    song_title: str = "",
    song_artist: str = "",
    model: str = "",
    api_key: str = "",
) -> Iterator[str]:
    """Yield prose for `prompt` in the classified tone, chunk by chunk."""
    from .classifier import build_client
    from .config import WRITER_MODEL

    user = _build_user(prompt, classification, song_title, song_artist)
    with build_client(api_key).messages.stream(
        model=model or WRITER_MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        yield from stream.text_stream


def write_in_tone(
    prompt: str,
    classification: ToneClassification,
    song_title: str = "",
    song_artist: str = "",
    model: str = "",
    api_key: str = "",
    on_text: Callable[[str], None] | None = None,
) -> str:
    """Generate prose for `prompt` in the classified tone.

    If `on_text` is provided, it's called with each chunk as it arrives (use it to
    print live). The full text is also returned.
    """
    chunks: list[str] = []
    for text in stream_in_tone(prompt, classification, song_title, song_artist, model, api_key):
        chunks.append(text)
        if on_text is not None:
            on_text(text)
    return "".join(chunks)
