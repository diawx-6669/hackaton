"""Фикстуры в форме реальных ответов Wikidata/Commons (сокращённые)."""
from __future__ import annotations

from typing import Any

QID = "Q1798175"
CATEGORY = "Category:Kazakh-British Technical University"

WBSEARCH: dict[str, Any] = {
    "search": [
        {
            "id": QID,
            "label": "Kazakh-British Technical University",
            "description": "university in Almaty, Kazakhstan",
            "match": {"type": "alias", "language": "ru", "text": "КБТУ"},
        },
        {
            "id": "Q99999",
            "label": "KBTU Business School",
            "description": "business school",
            "match": {"type": "label", "language": "en", "text": "KBTU Business School"},
        },
    ]
}

SPARQL: dict[str, Any] = {
    "results": {
        "bindings": [
            {
                "item": {"value": f"http://www.wikidata.org/entity/{QID}"},
                "itemLabel": {"value": "Казахстанско-Британский технический университет"},
                "itemDescription": {"value": "университет в Алматы"},
                "enLabel": {"value": "Kazakh-British Technical University"},
                "alias": {"value": "KBTU"},
                "coord": {"value": "Point(76.929 43.236)"},
                "website": {"value": "https://kbtu.edu.kz/"},
                "commonsCat": {"value": "Kazakh-British Technical University"},
                "cityLabel": {"value": "Алматы"},
                "countryLabel": {"value": "Казахстан"},
                "isEdu": {"value": "true"},
            },
            {
                "item": {"value": f"http://www.wikidata.org/entity/{QID}"},
                "itemLabel": {"value": "Казахстанско-Британский технический университет"},
                "alias": {"value": "КБТУ"},
                "isEdu": {"value": "true"},
            },
            {
                "item": {"value": "http://www.wikidata.org/entity/Q99999"},
                "itemLabel": {"value": "KBTU Business School"},
                "isEdu": {"value": "true"},
            },
        ]
    }
}


def _page(
    title: str,
    *,
    mime: str = "image/jpeg",
    width: int = 2048,
    height: int = 1365,
    lat: float | None = None,
    lon: float | None = None,
    license_: str | None = "CC BY-SA 4.0",
    author: str = "Jane Doe",
    categories: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    name = title.split(":", 1)[1].replace(" ", "_")
    extmeta: dict[str, Any] = {
        "Artist": {"value": f'<a href="/wiki/User:JD">{author}</a>'},
        "DateTimeOriginal": {"value": "2023-05-14 11:20:00"},
    }
    if description:
        extmeta["ImageDescription"] = {"value": description}
    if license_:
        extmeta["LicenseShortName"] = {"value": license_}
        extmeta["LicenseUrl"] = {"value": "https://creativecommons.org/licenses/by-sa/4.0/"}
    page: dict[str, Any] = {
        "title": title,
        "ns": 6,
        "imageinfo": [
            {
                "url": f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{name}",
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
                "thumburl": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{name}/640px-{name}",
                "user": author,
                "timestamp": "2023-05-14T11:20:00Z",
                "mime": mime,
                "width": width,
                "height": height,
                "extmetadata": extmeta,
            }
        ],
    }
    if categories:
        page["categories"] = [{"ns": 14, "title": f"Category:{c}"} for c in categories]
    if lat is not None and lon is not None:
        page["coordinates"] = [{"lat": lat, "lon": lon, "primary": ""}]
    return page


# Файл, найденный и в категории, и по геопоиску — проверяем склейку источников.
SHARED = "File:KBTU main building.jpg"

PAGES: dict[str, Any] = {
    SHARED: _page(
        SHARED,
        lat=43.2361,
        lon=76.9291,
        categories=["Kazakh-British Technical University"],
        description="Main building of the Kazakh-British Technical University",
    ),
    "File:KBTU library.jpg": _page(
        "File:KBTU library.jpg", categories=["Kazakh-British Technical University"]
    ),
    "File:KBTU dormitory.jpg": _page(
        "File:KBTU dormitory.jpg",
        categories=["Kazakh-British Technical University", "Dormitories in Almaty"],
    ),
    "File:KBTU logo.svg": _page("File:KBTU logo.svg", mime="image/svg+xml", width=512, height=512),
    "File:KBTU tiny.jpg": _page("File:KBTU tiny.jpg", width=120, height=90),
    "File:KBTU nolicense.jpg": _page("File:KBTU nolicense.jpg", license_=None),
    "File:Almaty far away.jpg": _page("File:Almaty far away.jpg", lat=43.30, lon=77.05),
}

# Малоизвестный вуз: ни категории Commons, ни координат — только имя.
OBSCURE_QID = "Q55555"
OBSCURE_NAME = "Kostanay Regional University"

OBSCURE_SPARQL: dict[str, Any] = {
    "results": {
        "bindings": [
            {
                "item": {"value": f"http://www.wikidata.org/entity/{OBSCURE_QID}"},
                "itemLabel": {"value": OBSCURE_NAME},
                "itemDescription": {"value": "university in Kazakhstan"},
                "isEdu": {"value": "true"},
            }
        ]
    }
}

OBSCURE_FILE = "File:Kostanay Regional University main hall.jpg"

COMMONS_FIXTURES: dict[str, Any] = {
    "categories": {
        CATEGORY: [
            {"title": SHARED, "ns": 6},
            {"title": "File:KBTU library.jpg", "ns": 6},
            {"title": "File:KBTU dormitory.jpg", "ns": 6},
            {"title": "File:KBTU logo.svg", "ns": 6},
            {"title": "File:KBTU tiny.jpg", "ns": 6},
            {"title": "File:KBTU nolicense.jpg", "ns": 6},
            {"title": "Category:KBTU buildings", "ns": 14},
        ],
        "Category:KBTU buildings": [{"title": SHARED, "ns": 6}],
    },
    "geosearch": [
        {"title": SHARED, "lat": 43.2361, "lon": 76.9291},
        {"title": "File:Almaty far away.jpg", "lat": 43.30, "lon": 77.05},
    ],
    "search": {
        "Kazakh-British Technical University": [{"title": SHARED}],
        OBSCURE_NAME: [{"title": OBSCURE_FILE}],
    },
    "pages": {
        **PAGES,
        OBSCURE_FILE: _page(OBSCURE_FILE, description=f"Main hall of the {OBSCURE_NAME}"),
    },
}
