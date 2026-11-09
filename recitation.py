"""Compare a recited (speech-to-text or typed) transcript with the original ayah."""

import re
from difflib import SequenceMatcher

# Tashkeel, Quranic annotation marks, small high letters, tatweel and dagger alef.
_DIACRITICS = re.compile(
    "[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u08D3-\u08FF]"
)
_NON_ARABIC = re.compile(r"[^\u0621-\u064A\s]")
_LETTER_MAP = str.maketrans(
    {
        "\u0622": "\u0627",  # آ -> ا
        "\u0623": "\u0627",  # أ -> ا
        "\u0625": "\u0627",  # إ -> ا
        "\u0671": "\u0627",  # ٱ -> ا
        "\u0649": "\u064A",  # ى -> ي
        "\u0629": "\u0647",  # ة -> ه
        "\u0624": "\u0621",  # ؤ -> ء
        "\u0626": "\u0621",  # ئ -> ء
    }
)

WORD_MATCH_THRESHOLD = 0.75
MEMORIZED_THRESHOLD = 0.85


def normalize_word(word: str) -> str:
    word = word.translate(_LETTER_MAP)
    word = _DIACRITICS.sub("", word)
    return _NON_ARABIC.sub("", word).strip()


def tokenize(text: str) -> list[str]:
    return [w for w in (normalize_word(t) for t in text.split()) if w]


def _similar(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= WORD_MATCH_THRESHOLD


def compare(expected_words: list[str], transcript: str) -> dict:
    """Align recited words against expected words.

    Returns per-word status ("correct" or "missed"), extra words that were
    recited but not in the ayah, an accuracy score and the memorized verdict.
    """
    # Some quran.com words contain a space (e.g. "يَا أَيُّهَا"), so align on
    # sub-tokens and map results back to the original words.
    expected: list[str] = []
    owner: list[int] = []
    for index, word in enumerate(expected_words):
        for token in tokenize(word):
            expected.append(token)
            owner.append(index)
    recited = tokenize(transcript)

    # Greedy in-order alignment with a small look-ahead so a single skipped or
    # misheard word does not shift every following word out of alignment.
    statuses = ["missed"] * len(expected)
    extras: list[str] = []
    i = j = 0
    lookahead = 3
    while i < len(expected) and j < len(recited):
        if _similar(expected[i], recited[j]):
            statuses[i] = "correct"
            i += 1
            j += 1
            continue
        skip_expected = next(
            (k for k in range(1, lookahead + 1)
             if i + k < len(expected) and _similar(expected[i + k], recited[j])),
            None,
        )
        skip_recited = next(
            (k for k in range(1, lookahead + 1)
             if j + k < len(recited) and _similar(expected[i], recited[j + k])),
            None,
        )
        if skip_expected is not None and (skip_recited is None or skip_expected <= skip_recited):
            i += skip_expected
        elif skip_recited is not None:
            extras.extend(recited[j:j + skip_recited])
            j += skip_recited
        else:
            extras.append(recited[j])
            i += 1
            j += 1
    extras.extend(recited[j:])

    word_statuses = ["correct"] * len(expected_words)
    for index, status in zip(owner, statuses):
        if status == "missed":
            word_statuses[index] = "missed"
    for index in set(range(len(expected_words))) - set(owner):
        word_statuses[index] = "missed"
    correct = word_statuses.count("correct")
    total = len(expected_words) or 1
    # Penalise extra words so reciting a different ayah does not pass.
    accuracy = correct / max(total, correct + len(extras) * 0.5)
    return {
        "words": word_statuses,
        "correct": correct,
        "total": len(expected_words),
        "extra_words": extras,
        "accuracy": round(accuracy, 3),
        "memorized": accuracy >= MEMORIZED_THRESHOLD,
    }
