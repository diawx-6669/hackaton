from app.models import Coordinates, Photo, RejectReason, SourceKind
from app.services import evidence

CAMPUS = Coordinates(lat=43.236, lon=76.929)


def make_photo(**kw) -> Photo:
    base = dict(
        id="x.jpg",
        title="x.jpg",
        url="https://upload.wikimedia.org/x.jpg",
        source_page_url="https://commons.wikimedia.org/wiki/File:x.jpg",
        source_kinds=[SourceKind.COMMONS_CATEGORY],
        license="CC BY-SA 4.0",
    )
    base.update(kw)
    return Photo(**base)


def test_haversine_known_distance():
    a = Coordinates(lat=43.236, lon=76.929)
    b = Coordinates(lat=43.245, lon=76.929)
    assert 990 < evidence.haversine_m(a, b) < 1010


def test_domain_trust_ranking():
    official, _ = evidence.domain_trust("https://kbtu.edu.kz/news/1", "https://kbtu.edu.kz/")
    commons_trust, _ = evidence.domain_trust("https://commons.wikimedia.org/wiki/File:x.jpg", None)
    unknown, _ = evidence.domain_trust("https://randomblog.example/x", None)
    stock, label = evidence.domain_trust("https://www.shutterstock.com/image/1", None)
    assert official == 1.0
    assert official > commons_trust > unknown > stock == 0.0
    assert "сток" in label


def test_stock_source_is_rejected():
    photo = make_photo(source_page_url="https://www.gettyimages.com/detail/1")
    scored = evidence.score_photo(photo, CAMPUS, None)
    assert scored.reject_reason is RejectReason.STOCK_DOMAIN
    assert evidence.bucket(scored) == "rejected"


def test_close_geotag_beats_missing_geotag():
    near = evidence.score_photo(
        make_photo(coordinates=Coordinates(lat=43.2361, lon=76.9291)), CAMPUS, None
    )
    no_geo = evidence.score_photo(make_photo(), CAMPUS, None)
    assert near.confidence > no_geo.confidence
    assert near.evidence.geo_distance_m is not None and near.evidence.geo_distance_m < 100
    assert any("нет геотега" in n for n in no_geo.evidence.notes)


def test_far_geotag_rejected():
    far = evidence.score_photo(
        make_photo(coordinates=Coordinates(lat=43.60, lon=77.40)), CAMPUS, None
    )
    assert far.reject_reason is RejectReason.TOO_FAR


def test_signals_are_explained_and_weighted():
    scored = evidence.score_photo(
        make_photo(coordinates=Coordinates(lat=43.2361, lon=76.9291)), CAMPUS, None
    )
    keys = {s.key for s in scored.evidence.signals}
    assert keys == {"geo", "domain", "category", "metadata", "sources"}
    assert all(s.detail for s in scored.evidence.signals)
    # Ни один сигнал не подмешивается молча: чего нет — то в notes.
    assert any("классификатор" in n.lower() for n in scored.evidence.notes)
    assert any("даты" in n.lower() for n in scored.evidence.notes)


def test_multi_source_photo_scores_higher():
    single = evidence.score_photo(make_photo(), CAMPUS, None)
    multi = evidence.score_photo(
        make_photo(source_kinds=[SourceKind.COMMONS_CATEGORY, SourceKind.COMMONS_GEOSEARCH]),
        CAMPUS,
        None,
    )
    assert multi.confidence > single.confidence


def test_university_name_in_metadata_is_an_evidence():
    from app.services.classify import mentions_university

    anonymous = evidence.score_photo(make_photo(), CAMPUS, None, ["Nazarbayev University"])
    named = evidence.score_photo(
        make_photo(
            title="Nazarbayev University main building.jpg",
            commons_categories=["Nazarbayev University"],
        ),
        CAMPUS,
        None,
        ["Nazarbayev University"],
    )
    assert named.confidence > anonymous.confidence
    assert named.evidence.name_mentions == ["Nazarbayev University"]
    assert anonymous.evidence.name_mentions == []
    # Аббревиатура ловится как отдельное слово, а не как подстрока.
    assert mentions_university("KBTU library.jpg", ["KBTU"]) == ["KBTU"]
    assert mentions_university("AKBTUS random.jpg", ["KBTU"]) == []


def test_stale_photo_is_flagged():
    old = evidence.score_photo(make_photo(date="1998-06-01 10:00:00"), CAMPUS, None)
    fresh = evidence.score_photo(make_photo(date="2025-06-01 10:00:00"), CAMPUS, None)
    assert old.stale is True and fresh.stale is False
    assert old.evidence.age_years and old.evidence.age_years > 20
    assert old.confidence < fresh.confidence


def test_geosearch_photo_without_any_link_is_rejected_as_wrong_university():
    stranger = evidence.score_photo(
        make_photo(
            title="Random apartment block.jpg",
            source_kinds=[SourceKind.COMMONS_GEOSEARCH],
            source_page_url="https://example.org/photo/1",
        ),
        CAMPUS,
        None,
        ["Nazarbayev University"],
    )
    assert stranger.reject_reason is RejectReason.NOT_THIS_UNIVERSITY
    assert "геопоиску" in stranger.reject_detail
