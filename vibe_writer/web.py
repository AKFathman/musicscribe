"""Web interface for Vibe Writer.

A thin Flask layer over the same classifier / songs / writer modules the CLI uses.
Run with:  python -m vibe_writer.web   (honours PORT, default 8000)

Endpoints:
  GET  /              -> the single-page UI
  POST /api/classify  -> tone classification for text or a song
  POST /api/recommend -> Mode 1 song pick for a piece of text
  POST /api/write     -> Mode 2 streamed prose in a given tone
"""

import os
from pathlib import Path

from .env import load_env

load_env()

from flask import Flask, Response, jsonify, request, stream_with_context

from .classifier import ToneClassification, classify_song, classify_text
from .songs import recommend_song
from .tones import TONE_DESCRIPTIONS, Tone
from .writer import stream_in_tone

_STATIC = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=None)


# --- error helpers ----------------------------------------------------------
def _is_key_error(exc: Exception) -> bool:
    name = type(exc).__name__
    msg = str(exc).lower()
    return name == "AuthenticationError" or "api_key" in msg or "anthropic_api_key" in msg


def _error_response(exc: Exception):
    if _is_key_error(exc):
        # A key was supplied (we pre-check for presence), so this means Anthropic
        # rejected it — invalid, expired, or lacking access.
        return (
            jsonify(
                error="Your Anthropic API key was rejected (invalid, expired, or without "
                "access to the requested model). Check the key and try again."
            ),
            401,
        )
    return jsonify(error=f"{type(exc).__name__}: {exc}"), 500


def _request_key() -> str:
    """The Anthropic key for this request: the visitor's key (header) wins, else the
    server's env key (if any). Read from a header, never the body, and never logged."""
    header_key = (request.headers.get("X-Anthropic-Key") or "").strip()
    return header_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _no_key_response():
    return (
        jsonify(
            error="No Anthropic API key provided. Add your key in the field at the top "
            "of the page — it stays in your browser and is used only for your requests."
        ),
        401,
    )


def _augment(clf: ToneClassification) -> dict:
    """Serialize a classification and attach human-readable tone descriptions."""
    data = clf.model_dump(mode="json")
    data["primary_description"] = TONE_DESCRIPTIONS[clf.primary_tone]
    data["secondary_description"] = (
        TONE_DESCRIPTIONS[clf.secondary_tone] if clf.secondary_tone is not None else None
    )
    return data


# --- routes -----------------------------------------------------------------
@app.get("/")
def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8"), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/healthz")
def healthz():
    # BYOK: visitors supply their own key. server_key just notes whether the host
    # also configured a fallback key in its own environment.
    return jsonify(ok=True, byok=True, server_key=bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()))


@app.post("/api/classify")
def api_classify():
    data = request.get_json(force=True, silent=True) or {}
    kind = data.get("kind")
    model = data.get("model", "")
    key = _request_key()
    if not key:
        return _no_key_response()
    try:
        if kind == "text":
            text = (data.get("text") or "").strip()
            if not text:
                return jsonify(error="No text provided."), 400
            clf = classify_text(text, model=model, api_key=key)
        elif kind == "song":
            title = (data.get("title") or "").strip()
            artist = (data.get("artist") or "").strip()
            if not (title and artist):
                return jsonify(error="Song title and artist are required."), 400
            clf = classify_song(title, artist, model=model, api_key=key)
        else:
            return jsonify(error="kind must be 'text' or 'song'."), 400
        return jsonify(_augment(clf))
    except Exception as exc:  # noqa: BLE001
        return _error_response(exc)


@app.post("/api/recommend")
def api_recommend():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text or "classification" not in data:
        return jsonify(error="Need 'text' and 'classification'."), 400
    key = _request_key()
    if not key:
        return _no_key_response()
    try:
        clf = ToneClassification.model_validate(data["classification"])
        rec = recommend_song(text, clf, model=data.get("model", ""), api_key=key)
        return jsonify(song=rec.song.model_dump(), explanation=rec.explanation)
    except Exception as exc:  # noqa: BLE001
        return _error_response(exc)


@app.post("/api/write")
def api_write():
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt or "classification" not in data:
        return jsonify(error="Need 'prompt' and 'classification'."), 400
    key = _request_key()
    if not key:
        return _no_key_response()
    try:
        clf = ToneClassification.model_validate(data["classification"])
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Invalid classification: {exc}"), 400

    title = (data.get("title") or "").strip()
    artist = (data.get("artist") or "").strip()
    model = data.get("model", "")

    def generate():
        try:
            yield from stream_in_tone(
                prompt, clf, song_title=title, song_artist=artist, model=model, api_key=key
            )
        except Exception as exc:  # noqa: BLE001
            # Surface errors inline in the stream so the UI can show them.
            prefix = "\n\n[error] "
            if _is_key_error(exc):
                yield prefix + "Your Anthropic API key was rejected (invalid, expired, or without model access)."
            else:
                yield prefix + f"{type(exc).__name__}: {exc}"

    return Response(stream_with_context(generate()), mimetype="text/plain; charset=utf-8")


def main():
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠  ANTHROPIC_API_KEY is not set — the UI will load but requests will fail.")
    print(f"Vibe Writer web server on http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
