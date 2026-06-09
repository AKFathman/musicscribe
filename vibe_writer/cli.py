"""Command-line interface for Vibe Writer.

Two modes:
  Mode 1  text  : a piece of writing -> its tone -> a song that matches it (+ why)
  Mode 2  song  : a song + a prompt   -> the song's tone -> your prompt written in it

Run with no arguments for an interactive menu.
"""

import argparse
import os
import sys

from .env import load_env

# Load .env if present (optional convenience).
load_env()


# --- tiny ANSI helpers (no dependency) -------------------------------------
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


def cyan(t: str) -> str:
    return _c("36", t)


def magenta(t: str) -> str:
    return _c("35", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def _rule(label: str = "") -> str:
    line = "─" * 56
    return dim(line) if not label else dim(f"── {label} " + "─" * (52 - len(label)))


def _print_classification(clf) -> None:
    from .tones import TONE_DESCRIPTIONS

    pct = f"{clf.confidence * 100:.0f}%"
    print(_rule("tone"))
    print(f"  {bold(magenta(clf.primary_tone.value))}  {dim(f'({pct} confidence)')}")
    print(f"  {dim(TONE_DESCRIPTIONS[clf.primary_tone])}")
    if clf.secondary_tone is not None:
        print(f"  {dim('+ undercurrent of')} {magenta(clf.secondary_tone.value)}")
    if clf.descriptors:
        print(f"  {dim('texture:')} {', '.join(clf.descriptors)}")
    print(f"  {dim('read:')} {clf.rationale}")


# --- modes ------------------------------------------------------------------
def run_text_mode(text: str, model: str = "") -> int:
    """Mode 1: writing -> tone -> matching song."""
    from .classifier import classify_text
    from .songs import recommend_song

    print(cyan("\nReading the vibe of your writing...\n"))
    clf = classify_text(text, model=model)
    _print_classification(clf)

    print(cyan("\nFinding a song that matches...\n"))
    rec = recommend_song(text, clf, model=model)

    print(_rule("song"))
    print(f"  {bold(green(rec.song.title))} {dim('—')} {green(rec.song.artist)}")
    print(f"  {dim('why:')} {rec.explanation}")
    print(_rule())
    return 0


def run_song_mode(title: str, artist: str, prompt: str, model: str = "", writer_model: str = "") -> int:
    """Mode 2: song -> tone -> prompt written in that tone."""
    from .classifier import classify_song
    from .writer import write_in_tone

    print(cyan(f'\nReading the vibe of "{title}" by {artist}...\n'))
    clf = classify_song(title, artist, model=model)
    _print_classification(clf)

    print(cyan("\nWriting your prompt in that tone...\n"))
    print(_rule("your piece"))

    def emit(chunk: str) -> None:
        sys.stdout.write(chunk)
        sys.stdout.flush()

    write_in_tone(
        prompt,
        clf,
        song_title=title,
        song_artist=artist,
        model=writer_model,
        on_text=emit,
    )
    print("\n" + _rule())
    return 0


# --- interactive ------------------------------------------------------------
def _read_multiline(label: str) -> str:
    print(dim(f"{label} (end with an empty line):"))
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def run_interactive() -> int:
    print(bold(magenta("\n🎵  Vibe Writer\n")))
    print("  [1] Text  → tone → a song that matches it")
    print("  [2] Song  → tone → write a prompt in that tone")
    choice = input("\nChoose a mode (1/2): ").strip()

    if choice == "1":
        text = _read_multiline("\nPaste your writing")
        if not text:
            print(yellow("Nothing to classify."))
            return 1
        return run_text_mode(text)
    elif choice == "2":
        title = input("\nSong title: ").strip()
        artist = input("Artist: ").strip()
        prompt = _read_multiline("\nWriting prompt")
        if not (title and artist and prompt):
            print(yellow("Need a song title, artist, and a prompt."))
            return 1
        return run_song_mode(title, artist, prompt)
    else:
        print(yellow("Unknown choice."))
        return 1


# --- argument parsing -------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vibe-writer",
        description="Classify the tone of writing or a song, and connect the two through music.",
    )
    p.add_argument(
        "--model",
        default="",
        help="Override the classification model (e.g. claude-haiku-4-5 for speed).",
    )
    sub = p.add_subparsers(dest="mode")

    t = sub.add_parser("text", help="Mode 1: writing -> tone -> a matching song.")
    src = t.add_mutually_exclusive_group()
    src.add_argument("text", nargs="?", help="The writing to classify (or use --file / stdin).")
    src.add_argument("--file", help="Read the writing from a file.")

    s = sub.add_parser("song", help="Mode 2: song + prompt -> write the prompt in the song's tone.")
    s.add_argument("--title", required=True, help="Song title.")
    s.add_argument("--artist", required=True, help="Song artist.")
    s.add_argument("--prompt", help="The writing prompt (or use --prompt-file / stdin).")
    s.add_argument("--prompt-file", help="Read the writing prompt from a file.")
    s.add_argument(
        "--writer-model",
        default="",
        help="Override the writing model for Mode 2 generation.",
    )
    return p


def _resolve_text(inline: str | None, file: str | None) -> str:
    if file:
        return open(file, encoding="utf-8").read().strip()
    if inline:
        return inline.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode is None:
        # No subcommand -> interactive menu.
        try:
            return run_interactive()
        except KeyboardInterrupt:
            print(yellow("\nCancelled."))
            return 130

    try:
        if args.mode == "text":
            text = _resolve_text(args.text, args.file)
            if not text:
                print(red("No text provided. Pass it inline, with --file, or via stdin."))
                return 1
            return run_text_mode(text, model=args.model)

        if args.mode == "song":
            prompt = _resolve_text(args.prompt, args.prompt_file)
            if not prompt:
                print(red("No prompt provided. Use --prompt, --prompt-file, or stdin."))
                return 1
            return run_song_mode(
                args.title, args.artist, prompt, model=args.model, writer_model=args.writer_model
            )
    except KeyboardInterrupt:
        print(yellow("\nCancelled."))
        return 130
    except Exception as exc:  # surface a clean message, not a traceback
        _print_error(exc)
        return 1

    parser.print_help()
    return 1


def _print_error(exc: Exception) -> None:
    import_error = isinstance(exc, ImportError)
    name = type(exc).__name__
    if import_error:
        print(red("Missing dependency: install with `pip install -r requirements.txt`."))
        return
    msg = str(exc)
    if "api_key" in msg.lower() or "ANTHROPIC_API_KEY" in msg or name == "AuthenticationError":
        print(red("No valid Anthropic API key found."))
        print(dim("Set ANTHROPIC_API_KEY in your environment or a .env file (see .env.example)."))
        return
    print(red(f"{name}: {msg}"))


if __name__ == "__main__":
    sys.exit(main())
