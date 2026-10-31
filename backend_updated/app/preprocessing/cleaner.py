"""Text cleaning utilities for customer feedback."""

import re
from functools import lru_cache

import emoji


NEGATION_TOKENS = frozenset({
    "no", "not", "never", "neither", "nor", "none", "nobody", "nothing",
    "nowhere", "hardly", "scarcely", "barely", "without", "cannot",
})

EMOJI_WORD_REPLACEMENTS = {
    "red heart": "love",
    "orange heart": "love",
    "yellow heart": "love",
    "green heart": "love",
    "blue heart": "love",
    "purple heart": "love",
    "black heart": "sad",
    "broken heart": "heartbreak",
    "thumbs up": "approve",
    "thumbs down": "disapprove",
    "clapping hands": "applause",
    "folded hands": "thanks",
    "face with tears of joy": "joy",
    "rolling on the floor laughing": "laugh",
    "loudly crying face": "sad",
    "crying face": "sad",
    "angry face": "angry",
    "pouting face": "angry",
    "face screaming in fear": "fear",
    "fearful face": "fear",
    "confused face": "confused",
    "face with rolling eyes": "annoyed",
    "fire": "fire",
    "collision": "impact",
    "100": "excellent",
    "check mark": "correct",
    "cross mark": "wrong",
}

CONTRACTION_REPLACEMENTS = {
    "can't": "can not",
    "cannot": "can not",
    "couldn't": "could not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "isn't": "is not",
    "mightn't": "might not",
    "mustn't": "must not",
    "needn't": "need not",
    "shouldn't": "should not",
    "wasn't": "was not",
    "weren't": "were not",
    "won't": "will not",
    "wouldn't": "would not",
}


@lru_cache(maxsize=1)
def get_nlp():
    """Load the English spaCy pipeline only when preprocessing is requested."""
    import spacy

    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' is not installed. "
            "Run: python -m spacy download en_core_web_sm"
        ) from exc


class TextCleaner:
    def clean(self, text: str) -> str:
        if text is None:
            return ""

        text = str(text).lower()
        for contraction, replacement in CONTRACTION_REPLACEMENTS.items():
            text = re.sub(rf"\b{re.escape(contraction)}\b", replacement, text)
        text = emoji.demojize(text, delimiters=(" ", " "))
        text = text.replace("_", " ")
        for emoji_words, replacement in EMOJI_WORD_REPLACEMENTS.items():
            text = re.sub(rf"\b{re.escape(emoji_words)}\b", replacement, text)
        text = re.sub(r"<.*?>", " ", text)
        text = re.sub(r"http\S+|www\S+", " ", text)
        text = re.sub(r"\S+@\S+", " ", text)
        text = re.sub(r"\d+", " ", text)
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
