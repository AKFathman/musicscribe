"""Runtime configuration.

Models are read from the environment so you can trade quality for speed/cost
without touching code. Defaults follow Anthropic's guidance: Opus 4.8 unless you
deliberately choose otherwise.

  VIBE_CLASSIFIER_MODEL   model used for tone classification + song selection
                          (classification is a simple task — set this to
                          claude-haiku-4-5 for a faster, cheaper, snappier CLI)
  VIBE_WRITER_MODEL       model used for Mode 2 prose generation
"""

import os

# Tone classification and song selection. Override with a faster model if you
# want a snappier CLI: export VIBE_CLASSIFIER_MODEL=claude-haiku-4-5
CLASSIFIER_MODEL = os.environ.get("VIBE_CLASSIFIER_MODEL", "claude-opus-4-8")

# Creative writing (Mode 2). Quality matters most here — keep this on Opus.
WRITER_MODEL = os.environ.get("VIBE_WRITER_MODEL", "claude-opus-4-8")
