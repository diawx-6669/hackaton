import pytest

from app.models import Coordinates, RejectReason, SourceKind
from app.services import commons
from tests import fixtures
from tests.conftest import COMMONS_API, commons_handler


@pytest.fixture
def commons_mock(api_mock):
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))
    return api_mock


async def test_category_files_walks_subcategories(commons_mock):
    files = await commons.category_files(fixtures.CATEGORY, depth=1)
    assert fixtures.SHARED in files
    assert "File:KBTU library.jpg" in files
    # Файл из подкатегории не должен задваиваться
    assert files.count(fixtures.SHARED) == 1


async def test_geosearch_files(commons_mock):
    files = await commons.geosearch_files(43.236, 76.929, radius=1000)
    assert fixtures.SHARED in files
    assert "File:Almaty far away.jpg" in files


async def test_collect_merges_sources_and_metadata(commons_mock):
    photos = await commons.collect(
        commons_category=fixtures.CATEGORY,
        coordinates=Coordinates(lat=43.236, lon=76.929),
    )
    by_id = {p.id: p for p in photos}

    shared = by_id["kbtu_main_building.jpg"]
    assert set(shared.source_kinds) == {
        SourceKind.COMMONS_CATEGORY,
        SourceKind.COMMONS_GEOSEARCH,
    }
    assert shared.author == "Jane Doe"
    assert shared.license == "CC BY-SA 4.0"
    assert shared.date.startswith("2023-05-14")
    assert shared.coordinates == Coordinates(lat=43.2361, lon=76.9291)
    assert shared.source_page_url.startswith("https://commons.wikimedia.org/wiki/File:")
    assert shared.thumb_url and "640px" in shared.thumb_url


async def test_collect_flags_non_photos(commons_mock):
    photos = await commons.collect(
        commons_category=fixtures.CATEGORY,
        coordinates=Coordinates(lat=43.236, lon=76.929),
    )
    by_id = {p.id: p for p in photos}
    assert by_id["kbtu_logo.svg"].reject_reason is RejectReason.NOT_A_PHOTO
    assert by_id["kbtu_tiny.jpg"].reject_reason is RejectReason.TOO_SMALL
    assert by_id["kbtu_nolicense.jpg"].reject_reason is RejectReason.NO_LICENSE
    assert by_id["kbtu_library.jpg"].reject_reason is None


def test_strip_html():
    assert commons.strip_html('<a href="#">Jane  Doe</a>') == "Jane Doe"
    assert commons.strip_html(None) is None


def test_file_id_is_stable():
    assert commons.file_id("File:KBTU Main Building.jpg") == "kbtu_main_building.jpg"
