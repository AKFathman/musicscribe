"""The shared tone taxonomy.

This is the hinge the whole tool turns on. Both modes classify into the *same*
vocabulary, so a song's vibe and a paragraph's vibe are expressed in the same
terms and can be mapped onto each other. Keep this list and the song library
(data/songs.json) in sync — every tone here should have candidate songs there.
"""

from enum import Enum


class Tone(str, Enum):
    MELANCHOLIC = "melancholic"
    EUPHORIC = "euphoric"
    TENSE = "tense"
    NOSTALGIC = "nostalgic"
    SERENE = "serene"
    DEFIANT = "defiant"
    ROMANTIC = "romantic"
    ANXIOUS = "anxious"
    TRIUMPHANT = "triumphant"
    WISTFUL = "wistful"
    BROODING = "brooding"
    PLAYFUL = "playful"
    HOPEFUL = "hopeful"
    SOMBER = "somber"
    ENERGETIC = "energetic"
    BITTERSWEET = "bittersweet"


# One-line guidance per tone, so the model classifies into a shared, well-defined
# space rather than inventing its own labels.
TONE_DESCRIPTIONS: dict[Tone, str] = {
    Tone.MELANCHOLIC: "a heavy, lingering sadness; grief or loss sat with quietly",
    Tone.EUPHORIC: "uncontainable joy, exhilaration, being swept up",
    Tone.TENSE: "coiled, on-edge, dread or suspense that hasn't broken yet",
    Tone.NOSTALGIC: "fond looking-back; warmth tinged with the pastness of the past",
    Tone.SERENE: "calm, still, at peace; unhurried and settled",
    Tone.DEFIANT: "resolve in the face of opposition; refusing to yield",
    Tone.ROMANTIC: "tender longing or devotion directed at another person",
    Tone.ANXIOUS: "restless worry, racing thoughts, unease without release",
    Tone.TRIUMPHANT: "victory, having overcome; earned elation and pride",
    Tone.WISTFUL: "gentle, yearning sadness for something distant or unreachable",
    Tone.BROODING: "dark, simmering introspection; smouldering rather than explosive",
    Tone.PLAYFUL: "light, mischievous, buoyant; not taking itself seriously",
    Tone.HOPEFUL: "forward-looking optimism; light breaking through",
    Tone.SOMBER: "grave, mournful, solemn; the weight of something serious",
    Tone.ENERGETIC: "kinetic drive and momentum; propulsive, restless motion",
    Tone.BITTERSWEET: "joy and sorrow held at once; the ache inside the sweetness",
}


def taxonomy_block() -> str:
    """Render the taxonomy as a stable text block for the system prompt.

    This is byte-stable across requests (sorted, fixed wording) so it can sit in
    the cached prefix — see classifier.py / writer.py.
    """
    lines = [f"- {tone.value}: {desc}" for tone, desc in TONE_DESCRIPTIONS.items()]
    return "\n".join(lines)


VALID_TONE_VALUES = [t.value for t in Tone]
