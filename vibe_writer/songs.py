"""The song library and song-selection logic for Mode 1.

The library (data/songs.json) is a curated map of tone -> real, well-known songs.
Pulling from a fixed library (rather than asking the model to free-associate a
song) guarantees the recommendation is a real song, not a hallucinated one. The
model's job is narrower and more reliable: pick the best fit from the candidates
for the classified tone, and explain it in terms of the user's actual writing.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .classifier import ToneClassification
from .tones import Tone

_SONGS_PATH = Path(__file__).parent / "data" / "songs.json"


class Song(BaseModel):
    title: str
    artist: str
    note: str


@lru_cache(maxsize=1)
def _library() -> dict[str, list[Song]]:
    raw = json.loads(_SONGS_PATH.read_text(encoding="utf-8"))
    return {tone: [Song(**s) for s in songs] for tone, songs in raw.items()}


def candidates_for(classification: ToneClassification) -> list[Song]:
    """Gather candidate songs for the classified tone (primary first, then secondary)."""
    lib = _library()
    songs: list[Song] = list(lib.get(classification.primary_tone.value, []))
    if classification.secondary_tone is not None:
        for song in lib.get(classification.secondary_tone.value, []):
            if not any(s.title == song.title and s.artist == song.artist for s in songs):
                songs.append(song)
    return songs


class SongPick(BaseModel):
    """The model's choice of best-fit song from the candidate list."""

    choice_index: int = Field(description="0-based index of the chosen song in the candidate list.")
    explanation: str = Field(
        description="2–4 sentences on why this song matches the tone AND the specific text, "
        "referencing concrete details of both."
    )


class SongRecommendation(BaseModel):
    """The full Mode 1 result handed back to the CLI."""

    classification: ToneClassification
    song: Song
    explanation: str


def recommend_song(
    text: str, classification: ToneClassification, model: str = "", api_key: str = ""
) -> SongRecommendation:
    """Pick the best-fit song for the text from the classified tone's candidates."""
    from .classifier import build_client
    from .config import CLASSIFIER_MODEL

    candidates = candidates_for(classification)
    if not candidates:
        raise RuntimeError(
            f"No songs in the library for tone '{classification.primary_tone.value}'. "
            "Check data/songs.json."
        )

    listing = "\n".join(
        f"[{i}] \"{s.title}\" by {s.artist} — {s.note}" for i, s in enumerate(candidates)
    )
    secondary = (
        classification.secondary_tone.value if classification.secondary_tone else "none"
    )

    system = (
        "You are a music supervisor. Given a piece of writing, its classified tone, "
        "and a shortlist of candidate songs, pick the ONE song that best captures the "
        "writing's vibe. Choose by emotional fit, not popularity. Explain the choice by "
        "tying concrete details of the song to concrete details of the writing."
    )
    user = (
        f"Tone: {classification.primary_tone.value} (secondary: {secondary})\n"
        f"Descriptors: {', '.join(classification.descriptors)}\n\n"
        "--- BEGIN TEXT ---\n"
        f"{text.strip()}\n"
        "--- END TEXT ---\n\n"
        "Candidate songs:\n"
        f"{listing}\n\n"
        "Choose the single best fit by its index."
    )

    resp = build_client(api_key).messages.parse(
        model=model or CLASSIFIER_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=SongPick,
    )
    pick: Optional[SongPick] = resp.parsed_output
    if pick is None:
        raise RuntimeError("Song selection did not return structured output. Try again.")

    # Guard against an out-of-range index from the model.
    idx = pick.choice_index if 0 <= pick.choice_index < len(candidates) else 0
    return SongRecommendation(
        classification=classification,
        song=candidates[idx],
        explanation=pick.explanation,
    )
