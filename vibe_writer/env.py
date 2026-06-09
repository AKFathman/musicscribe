"""Environment loading.

Loads a local .env if present. Handles the common gotcha where the shell exports
ANTHROPIC_API_KEY as an empty string: dotenv won't override an already-present
(even if blank) variable by default, which would silently mask a real key placed
in .env. So if the key is missing or blank after a normal load, we re-load with
override=True so .env wins.
"""

import os


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        # Present-but-blank or absent — let .env take precedence.
        load_dotenv(override=True)
