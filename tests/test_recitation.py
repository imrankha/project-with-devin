from recitation import compare, normalize_word

FATIHA_2 = ["الْحَمْدُ", "لِلَّهِ", "رَبِّ", "الْعَالَمِينَ"]


def test_normalize_strips_diacritics_and_unifies_letters():
    assert normalize_word("ٱلرَّحْمَـٰنِ") == "الرحمن"
    assert normalize_word("إِلَىٰ") == "الي"
    assert normalize_word("الْعَالَمِينَ") == "العالمين"


def test_exact_recitation_is_memorized():
    result = compare(FATIHA_2, "الحمد لله رب العالمين")
    assert result["memorized"] is True
    assert result["words"] == ["correct"] * 4
    assert result["accuracy"] == 1.0


def test_missing_word_is_flagged():
    result = compare(FATIHA_2, "الحمد لله العالمين")
    assert result["words"] == ["correct", "correct", "missed", "correct"]
    assert result["memorized"] is False


def test_small_spelling_variation_is_tolerated():
    result = compare(FATIHA_2, "الحمد لله رب العلمين")
    assert result["memorized"] is True


def test_wrong_ayah_is_not_memorized():
    result = compare(FATIHA_2, "قل هو الله احد الله الصمد")
    assert result["memorized"] is False
    assert result["accuracy"] < 0.6


def test_extra_words_reduce_accuracy():
    result = compare(FATIHA_2, "الحمد لله رب العالمين قل هو الله احد الصمد لم يلد")
    assert result["words"] == ["correct"] * 4
    assert result["extra_words"]
    assert result["memorized"] is False


def test_expected_word_with_space_matches_split_transcript():
    words = ["يَا أَيُّهَا", "الْمُزَّمِّلُ"]
    result = compare(words, "يا ايها المزمل")
    assert result["memorized"]
    assert result["words"] == ["correct", "correct"]
    assert result["accuracy"] == 1.0


def test_accuracy_counts_whole_words():
    words = ["يَا أَيُّهَا", "الَّذِينَ", "آمَنُوا", "اتَّقُوا", "اللَّهَ", "حَقَّ"]
    result = compare(words, "يا ايها الذين امنوا اتقوا الله")
    assert result["correct"] == 5
    assert not result["memorized"]
