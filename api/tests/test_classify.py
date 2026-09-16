from app.models import Photo, PhotoCategory
from app.services.classify import classify, mentions_university


def photo(title: str, categories: list[str] | None = None, description: str = "") -> Photo:
    return Photo(
        id=title.lower(),
        title=title,
        url=f"https://upload.wikimedia.org/{title}",
        source_page_url=f"https://commons.wikimedia.org/wiki/File:{title}",
        commons_categories=categories or [],
        description=description,
    )


def test_specific_categories_win_over_campus():
    cases = {
        "KBTU dormitory block B.jpg": PhotoCategory.DORMS,
        "Main library reading room.jpg": PhotoCategory.LIBRARIES,
        "Chemistry laboratory of the university.jpg": PhotoCategory.LABS,
        "University swimming pool.jpg": PhotoCategory.SPORTS,
        "Lecture hall 201.jpg": PhotoCategory.CLASSROOMS,
        "Graduation ceremony 2019.jpg": PhotoCategory.STUDENT_LIFE,
    }
    for title, expected in cases.items():
        assert classify(photo(title)).category is expected, title


def test_campus_and_city_are_fallbacks():
    assert classify(photo("University main building facade.jpg")).category is PhotoCategory.CAMPUS
    assert classify(photo("Panorama of Almaty city.jpg")).category is PhotoCategory.CITY


def test_junk_is_detected():
    for title in (
        "KBTU logo.png",
        "Coat of arms of the university.png",
        "Map of the campus area.jpg",
        "Diploma certificate scan.jpg",
        "Portrait of the rector.jpg",
    ):
        result = classify(photo(title))
        assert result.is_junk, title
        assert result.category is PhotoCategory.JUNK
        assert result.matched


def test_commons_categories_are_used_as_signal():
    result = classify(photo("IMG 20190412.jpg", categories=["Dormitories in Almaty"]))
    assert result.category is PhotoCategory.DORMS
    assert result.confidence > 0.35


def test_unknown_when_nothing_matches():
    assert classify(photo("IMG 0042.jpg")).category is PhotoCategory.UNKNOWN


def test_metadata_confidence_is_capped():
    result = classify(
        photo(
            "University library reading room library.jpg",
            categories=["Libraries", "Library interiors"],
            description="library of the university, reading room",
        )
    )
    assert result.confidence <= 0.85, "эвристика не имеет права быть уверенной на 100%"


def test_mentions_university_handles_multiword_and_acronyms():
    assert mentions_university("Al-Farabi Kazakh National University gate", ["Kazakh National University"])
    assert mentions_university("KazNU building", ["KazNU"]) == ["KazNU"]
    assert mentions_university("SomeKazNUthing", ["KazNU"]) == []
