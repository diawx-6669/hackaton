import httpx
import pytest

from app.services import wikidata
from tests import fixtures
from tests.conftest import WIKIDATA_API, WIKIDATA_SPARQL


@pytest.fixture
def wikidata_mock(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    return api_mock


async def test_resolve_returns_university_with_metadata(wikidata_mock):
    results = await wikidata.resolve("КБТУ")
    assert results, "ожидали хотя бы одного кандидата"
    top = results[0]
    assert top.id == fixtures.QID
    assert top.city == "Алматы"
    assert top.website == "https://kbtu.edu.kz/"
    assert top.commons_category == "Kazakh-British Technical University"
    assert top.coordinates is not None
    assert round(top.coordinates.lat, 3) == 43.236
    assert round(top.coordinates.lon, 3) == 76.929
    assert top.wikidata_url.endswith(fixtures.QID)


async def test_resolve_marks_ambiguity(wikidata_mock):
    results = await wikidata.resolve("KBTU")
    assert len(results) >= 2
    assert wikidata.is_ambiguous(results) is True


async def test_resolve_empty_on_no_hits(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json={"search": []}))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json={"results": {"bindings": []}}))
    assert await wikidata.resolve("нетакоговуза") == []


async def test_resolve_survives_sparql_failure(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(500))
    results = await wikidata.resolve("КБТУ")
    # Без SPARQL остаётся текстовая эвристика: вуз всё равно найден, но без координат.
    assert results and results[0].coordinates is None


def test_parse_point():
    c = wikidata.parse_point("Point(76.929 43.236)")
    assert c is not None and (c.lat, c.lon) == (43.236, 76.929)
    assert wikidata.parse_point(None) is None


async def test_aliases_and_english_label_are_collected(wikidata_mock):
    """Английское имя и аббревиатура — главная улика для файлов Commons."""
    top = (await wikidata.resolve("КБТУ"))[0]
    assert "Kazakh-British Technical University" in top.aliases
    assert "KBTU" in top.aliases
    assert "КБТУ" in top.aliases
    assert top.name not in top.aliases, "название не должно дублироваться в алиасах"


async def test_untyped_university_is_shown_rather_than_hidden(api_mock):
    """У малоизвестных вузов тип в Wikidata часто не проставлен.

    Показать сомнительного кандидата честнее, чем сказать «ничего не найдено».
    """
    api_mock.get(WIKIDATA_API).mock(
        return_value=httpx.Response(
            200,
            json={
                "search": [
                    {"id": "Q777", "label": "Aktobe Regional University", "description": None}
                ]
            },
        )
    )
    # SPARQL не вернул ни типа, ни описания.
    api_mock.get(WIKIDATA_SPARQL).mock(
        return_value=httpx.Response(200, json={"results": {"bindings": []}})
    )
    results = await wikidata.resolve("Aktobe Regional University")
    assert [u.id for u in results] == ["Q777"]


async def test_non_education_item_is_still_filtered_out(api_mock):
    """А вот явное «не учебное заведение» показывать нельзя."""
    api_mock.get(WIKIDATA_API).mock(
        return_value=httpx.Response(
            200, json={"search": [{"id": "Q888", "label": "Almaty", "description": "city"}]}
        )
    )
    api_mock.get(WIKIDATA_SPARQL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q888"},
                            "itemLabel": {"value": "Almaty"},
                            "isEdu": {"value": "false"},
                        }
                    ]
                }
            },
        )
    )
    assert await wikidata.resolve("Almaty") == []


# --- запасной путь: SPARQL лежит, данные берём из Action API ---

WBGETENTITIES_UNI = {
    "entities": {
        fixtures.QID: {
            "id": fixtures.QID,
            "labels": {
                "ru": {"language": "ru", "value": "Казахстанско-Британский технический университет"},
                "en": {"language": "en", "value": "Kazakh-British Technical University"},
            },
            "descriptions": {"ru": {"language": "ru", "value": "университет в Алматы"}},
            "aliases": {"en": [{"language": "en", "value": "KBTU"}]},
            "claims": {
                "P31": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": "Q3918"}}}}],
                "P625": [
                    {
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {"value": {"latitude": 43.2359, "longitude": 76.9455}},
                        }
                    }
                ],
                "P856": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": "https://kbtu.edu.kz/"}}}],
                "P373": [
                    {
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {"value": "Kazakh-British Technical University"},
                        }
                    }
                ],
                "P571": [
                    {
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {"value": {"time": "+2001-01-01T00:00:00Z"}},
                        }
                    }
                ],
                "P154": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": "KBTU logo.png"}}}],
                "P131": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": "Q1520"}}}}],
                "P17": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": "Q232"}}}}],
            },
        }
    }
}

WBGETENTITIES_PLACES = {
    "entities": {
        "Q1520": {
            "id": "Q1520",
            "labels": {"ru": {"language": "ru", "value": "Алматы"}},
            "claims": {
                "P625": [
                    {
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {"value": {"latitude": 43.25, "longitude": 76.95}},
                        }
                    }
                ]
            },
        },
        "Q232": {"id": "Q232", "labels": {"ru": {"language": "ru", "value": "Казахстан"}}, "claims": {}},
    }
}


def _action_handler(request: httpx.Request) -> httpx.Response:
    """wbsearchentities отдаёт поиск, wbgetentities — карточку или места."""
    action = request.url.params.get("action")
    if action == "wbsearchentities":
        return httpx.Response(200, json=fixtures.WBSEARCH)
    ids = request.url.params.get("ids", "")
    if "Q1520" in ids or "Q232" in ids:
        return httpx.Response(200, json=WBGETENTITIES_PLACES)
    return httpx.Response(200, json=WBGETENTITIES_UNI)


@pytest.fixture
def sparql_down(api_mock):
    """SPARQL отвечает 403 — ровно то, что делает Wikidata при лимитах."""
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(403, text="Forbidden"))
    api_mock.get(WIKIDATA_API).mock(side_effect=_action_handler)
    return api_mock


async def test_details_fall_back_to_action_api(sparql_down):
    details = await wikidata.fetch_details([fixtures.QID])
    rec = details[fixtures.QID]

    assert rec["label"] == "Казахстанско-Британский технический университет"
    assert rec["en_label"] == "Kazakh-British Technical University"
    assert "KBTU" in rec["aliases"]
    assert rec["coord"] == "Point(76.9455 43.2359)"
    assert rec["website"] == "https://kbtu.edu.kz/"
    assert rec["commons_category"] == "Kazakh-British Technical University"
    assert rec["inception"].startswith("2001-01-01")
    assert rec["logo"].endswith("KBTU_logo.png")
    assert rec["city"] == "Алматы"
    assert rec["country"] == "Казахстан"
    assert rec["city_coord"] == "Point(76.95 43.25)"
    assert rec["is_edu"] is True


async def test_resolve_survives_sparql_outage(sparql_down):
    """Главное: при 403 от SPARQL профиль всё равно собирается."""
    results = await wikidata.resolve("КБТУ")
    assert results
    top = results[0]
    assert top.id == fixtures.QID
    assert top.city == "Алматы"
    assert top.commons_category == "Kazakh-British Technical University"
    assert top.coordinates is not None and round(top.coordinates.lat, 3) == 43.236
