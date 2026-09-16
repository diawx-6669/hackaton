from app.services.textmatch import expand_query, normalize, similarity, translit_cyr_to_lat


def test_normalize_strips_punctuation_and_case():
    assert normalize("  КазНУ им. аль-Фараби! ") == "казну им аль фараби"


def test_translit():
    assert translit_cyr_to_lat("кбту") == "kbtu"


def test_expand_query_adds_known_abbreviation():
    variants = expand_query("КБТУ")
    assert variants[0] == "КБТУ"
    assert any("Kazakh-British" in v for v in variants)


def test_expand_query_transliterates_unknown_acronym():
    variants = expand_query("СКГУ")
    assert "skgu" in variants


def test_similarity_matches_acronym_to_initials():
    score = similarity("KBTU", "Kazakh British Technical University")
    assert score > 0.9


def test_similarity_cross_alphabet():
    assert similarity("МГУ", "Moscow State University") > 0.5
    assert similarity("Nazarbayev University", "Nazarbayev University") == 1.0


def test_similarity_rejects_unrelated():
    assert similarity("KBTU", "Harvard University") < 0.6
