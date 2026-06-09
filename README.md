# 🎵 Vibe Writer

Vibe Writer connects **writing** and **music** through a shared vocabulary of tone.
It runs in two directions:

- **Mode 1 — Text → Tone → Song.** Give it a piece of writing. It classifies the
  vibe (e.g. *melancholic*, *euphoric*, *tense*, *nostalgic*) and recommends a song
  that matches, explaining why.
- **Mode 2 — Song + Prompt → Writing.** Give it a song (title + artist) and a
  writing prompt. It classifies the song's vibe and writes your prompt *in that tone*.

Both modes are powered by the **Anthropic Claude API**.

---

## How it works (architecture)

The two modes are two halves of one system, joined by a **shared tone taxonomy** —
a fixed set of 16 vibes defined in [`vibe_writer/tones.py`](vibe_writer/tones.py).
Everything classifies into the *same* vocabulary, so a song's vibe and a paragraph's
vibe are directly comparable.

```
                          ┌─────────────────────────────┐
                          │   shared tone taxonomy      │
                          │  (16 vibes, tones.py)       │
                          └──────────────┬──────────────┘
                                         │
        Mode 1                           │                         Mode 2
  ┌───────────────┐                      │                  ┌───────────────┐
  │ your writing  │                      │                  │ song + prompt │
  └──────┬────────┘                      │                  └──────┬────────┘
         │ classify_text()               │                         │ classify_song()
         ▼                               ▼                         ▼
   ToneClassification ────────► (one classifier) ◄──────── ToneClassification
         │                                                         │
         │ look up tone in song library                            │ feed tone to writer
         ▼                                                         ▼
   recommend_song()  ──►  a real song + explanation        write_in_tone()  ──►  streamed prose
```

**Design decisions:**

1. **LLM-based classification, not a trained model.** Tone is subtle, open-vocabulary,
   and (for songs especially) needs world knowledge the model already has. Constraining
   the output to a fixed `enum` via Claude's **structured outputs** (`messages.parse`
   + Pydantic) gives the consistency of a classifier with no training data or model to
   maintain. See [`classifier.py`](vibe_writer/classifier.py).

2. **A curated song library, not free association.** Songs live in
   [`vibe_writer/data/songs.json`](vibe_writer/data/songs.json), tagged by tone. Mode 1
   classifies the text, then asks Claude to pick the best fit *from the real candidates*
   for that tone and explain it against the user's specific writing. This guarantees a
   real song (no hallucinated titles) while keeping the explanation grounded. See
   [`songs.py`](vibe_writer/songs.py).

3. **Streaming generation for Mode 2.** Prose is streamed token-by-token so the CLI
   stays responsive. See [`writer.py`](vibe_writer/writer.py).

4. **Prompt caching + model tiers.** Stable system prefixes (the taxonomy, the writing
   instructions) are marked cacheable. Classification defaults to Opus 4.8 but can be
   dropped to Haiku for a faster, cheaper CLI via an env var (see Configuration).

---

## Setup

Requires **Python 3.10+** and an Anthropic API key.

```bash
cd vibe-writer

# 1. (recommended) create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. install dependencies
pip install -r requirements.txt

# 3. provide your API key — either export it...
export ANTHROPIC_API_KEY=sk-ant-...
#    ...or copy the template and fill it in (auto-loaded via python-dotenv):
cp .env.example .env   # then edit .env
```

Optionally install it as a `vibe-writer` command: `pip install -e .`

---

## Usage

You can run it as a module (`python -m vibe_writer`) or, if installed with
`pip install -e .`, as `vibe-writer`.

### Interactive (easiest)

```bash
python -m vibe_writer
```

Pick a mode from the menu and follow the prompts.

### Mode 1 — Text → Tone → Song

```bash
# inline
python -m vibe_writer text "The streets were empty. I kept walking anyway, collar up against a rain that wasn't coming."

# from a file
python -m vibe_writer text --file my_essay.txt

# from stdin / a pipe
cat my_essay.txt | python -m vibe_writer text
```

Output: the classified tone (with confidence, texture, and a one-line read) and a
recommended song with an explanation tying it to your writing.

### Mode 2 — Song + Prompt → Writing

```bash
python -m vibe_writer song \
  --title "Mr. Brightside" --artist "The Killers" \
  --prompt "Describe a morning commute on a crowded train."

# the prompt can also come from a file or stdin
python -m vibe_writer song --title "Hurt" --artist "Johnny Cash" --prompt-file prompt.txt
```

Output: the song's classified tone, then your prompt written in that tone (streamed).

---

## Web app & public link

The same logic is also exposed as a small Flask web app (`vibe_writer/web.py`) with
a single-page UI — Mode 2 streams the generated prose token-by-token in the browser.

Run it locally:

```bash
python -m vibe_writer.web          # serves on http://localhost:8000 (set PORT to change)
```

Expose it on a free public URL with a [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
quick tunnel (`brew install cloudflared`):

```bash
./serve_public.sh                  # starts the server + tunnel, prints the public https URL
```

The script prints a `https://<random>.trycloudflare.com` link that stays live while
the process runs.

### Bring-your-own-key (BYOK)

The web app is **BYOK**: each visitor enters their own Anthropic API key in a field
on the page. The key is:

- stored only in **that visitor's browser** (`localStorage`);
- sent over HTTPS in an `X-Anthropic-Key` header with each request;
- used per-request, in memory, to call Claude on their behalf — **never stored or
  logged** on the server.

Because every visitor uses their own key, the host's API credits are never spent,
and the server needs no key of its own. (If you *do* set `ANTHROPIC_API_KEY` in the
server's environment, it's used only as a fallback when a request arrives without a
key — leave it unset for a purely public, self-service deployment.)

> Note: the server does proxy each request, so a visitor's key passes through the
> host in memory for the duration of that request. Only share the link with people
> comfortable with that, and prefer running it somewhere you control.

---

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key. |
| `VIBE_CLASSIFIER_MODEL` | `claude-opus-4-8` | Model for tone classification + song selection. Set to `claude-haiku-4-5` for a faster, cheaper, snappier CLI. |
| `VIBE_WRITER_MODEL` | `claude-opus-4-8` | Model for Mode 2 prose generation. |
| `NO_COLOR` | — | Set to disable ANSI colors. |

Per-invocation overrides are also available: `--model` (classification) and
`--writer-model` (Mode 2 generation).

---

## Extending the song library

Add or edit entries in [`vibe_writer/data/songs.json`](vibe_writer/data/songs.json).
Keys must be tone values from the taxonomy in `tones.py`; each song needs a `title`,
`artist`, and a short `note` describing its feel. Keep every taxonomy tone populated
with a few candidates.

---

## Project layout

```
vibe-writer/
├── vibe_writer/
│   ├── tones.py        # shared tone taxonomy (the hinge between both modes)
│   ├── classifier.py   # LLM tone classification (structured outputs)
│   ├── songs.py        # song library + Mode 1 selection logic
│   ├── writer.py       # Mode 2 streamed generation
│   ├── cli.py          # command-line interface
│   ├── config.py       # model configuration
│   └── data/songs.json # curated tone → songs library
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```
