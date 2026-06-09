"""LLM-based tone classification.

One classifier serves both modes. It maps either a piece of writing or a song
(title + artist) into the shared tone taxonomy, returning a validated, structured
result via Claude's structured-output support (`messages.parse` + Pydantic).

Why an LLM rather than a trained classifier: tone/vibe is subtle, open-vocabulary,
and needs world knowledge (especially for songs — the model already "knows" what
"Hurt" by Johnny Cash feels like). Constraining the output to a fixed enum gives
us the consistency of a classifier without training data or a model to maintain.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .tones import Tone, taxonomy_block


class ToneClassification(BaseModel):
    """Structured result of classifying a piece of text or a song."""

    primary_tone: Tone = Field(description="The single dominant tone, from the taxonomy.")
    secondary_tone: Optional[Tone] = Field(
        default=None,
        description="An optional secondary tone if the vibe is layered; null if not.",
    )
    confidence: float = Field(description="Confidence in the primary tone, 0.0–1.0.")
    descriptors: list[str] = Field(
        description="3–6 vivid adjectives capturing the specific feel (free vocabulary)."
    )
    rationale: str = Field(description="One or two sentences explaining the read.")


# Stable system prefix — byte-identical across every classification request, so it
# can live in the cached prompt prefix. The per-request, varying content (the text
# or the song) goes in the user turn, never here.
_SYSTEM = f"""You are a careful tone-and-vibe classifier for the Vibe Writer tool.

Classify the emotional tone of the input into this fixed taxonomy. Choose the
single best primary tone. Add a secondary tone only if the piece genuinely carries
a second, distinct layer; otherwise leave it null.

Taxonomy:
{taxonomy_block()}

Rules:
- primary_tone and secondary_tone MUST be values from the taxonomy above.
- descriptors are free-vocabulary adjectives (e.g. "hollow", "shimmering",
  "white-knuckle") that pin down the *specific* shade beyond the broad label.
- Be decisive but honest: set confidence lower when the vibe is ambiguous or mixed.
- Judge the actual emotional texture, not the surface subject matter."""


def build_client(api_key: str = ""):
    """Construct an Anthropic client.

    If `api_key` is given (e.g. a per-user key from the web UI) it's used directly;
    otherwise the SDK falls back to the ANTHROPIC_API_KEY environment variable.
    Imported lazily so `--help` and unit tests don't require the SDK or a key.
    """
    import anthropic

    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def _classify(user_content: str, model: str, api_key: str = "") -> ToneClassification:
    from .config import CLASSIFIER_MODEL

    resp = build_client(api_key).messages.parse(
        model=model or CLASSIFIER_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
        output_format=ToneClassification,
    )
    result = resp.parsed_output
    if result is None:
        raise RuntimeError(
            f"Classification did not return structured output (stop_reason="
            f"{resp.stop_reason!r}). Try again or rephrase the input."
        )
    return result


def classify_text(text: str, model: str = "", api_key: str = "") -> ToneClassification:
    """Classify the tone of a piece of writing."""
    user = (
        "Classify the tone of the following piece of writing.\n\n"
        "--- BEGIN TEXT ---\n"
        f"{text.strip()}\n"
        "--- END TEXT ---"
    )
    return _classify(user, model, api_key)


def classify_song(title: str, artist: str, model: str = "", api_key: str = "") -> ToneClassification:
    """Classify the overall emotional vibe of a song from its title and artist.

    The model draws on what it knows about the song — lyrics, instrumentation,
    delivery, and cultural feel — to read its dominant tone.
    """
    user = (
        "Classify the overall emotional vibe of this song, considering its lyrics, "
        "instrumentation, delivery, and mood as a whole.\n\n"
        f"Song: \"{title.strip()}\"\n"
        f"Artist: {artist.strip()}"
    )
    return _classify(user, model, api_key)
