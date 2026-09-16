"""Нормализация запроса, транслитерация и синонимы/аббревиатуры вузов.

Важно: здесь живёт ТОЛЬКО расширение поискового запроса. Никаких готовых
результатов — сами вузы и фото всегда ищутся в Wikidata/Commons на лету.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    # казахские буквы
    "ә": "a", "ғ": "g", "қ": "q", "ң": "n", "ө": "o", "ұ": "u", "ү": "u",
    "һ": "h", "і": "i",
}

# Обратная карта для латиницы, набранной вместо кириллицы (для аббревиатур).
_LAT2CYR = {
    "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "z": "з",
    "i": "и", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х", "c": "ц",
    "y": "у", "q": "қ", "j": "ж", "w": "в", "x": "кс",
}

# Сидовый словарь аббревиатур: только РАСШИРЕНИЕ ЗАПРОСА, не результаты.
# Wikidata сама знает большинство алиасов, это подстраховка для частых кейсов.
ABBREVIATIONS: dict[str, list[str]] = {
    "кбту": ["KBTU", "Kazakh-British Technical University"],
    "kbtu": ["Kazakh-British Technical University", "КБТУ"],
    "назарбаев": ["Nazarbayev University"],
    "ну": ["Nazarbayev University"],
    "nu": ["Nazarbayev University"],
    "казну": ["Al-Farabi Kazakh National University", "KazNU"],
    "kaznu": ["Al-Farabi Kazakh National University"],
    "сду": ["SDU University", "Suleyman Demirel University"],
    "sdu": ["Suleyman Demirel University"],
    "аиту": ["Astana IT University", "AITU"],
    "aitu": ["Astana IT University"],
    "енu": ["L.N. Gumilyov Eurasian National University"],
    "ену": ["L.N. Gumilyov Eurasian National University", "ENU"],
    "сатпаев": ["Satbayev University", "Kazakh National Research Technical University"],
    "казнту": ["Satbayev University"],
    "мгу": ["Moscow State University", "Московский государственный университет"],
    "msu": ["Moscow State University"],
    "спбгу": ["Saint Petersburg State University"],
    "мфти": ["Moscow Institute of Physics and Technology", "MIPT"],
    "мифи": ["National Research Nuclear University MEPhI"],
    "вшэ": ["HSE University", "Higher School of Economics"],
    "hse": ["HSE University"],
    "мит": ["Massachusetts Institute of Technology", "MIT"],
    "mit": ["Massachusetts Institute of Technology"],
    "нархоз": ["Narxoz University"],
    "кимэп": ["KIMEP University"],
    "kimep": ["KIMEP University"],
    # Региональные и менее известные вузы Казахстана
    "кету": ["Kazakh University of Economics"],
    "кгу": ["Karaganda State University", "Kostanay State University"],
    "карту": ["Karaganda Technical University"],
    "кргу": ["Karaganda Buketov University"],
    "югу": ["South Kazakhstan University"],
    "юкгу": ["M. Auezov South Kazakhstan University"],
    "вкгу": ["Sarsen Amanzholov East Kazakhstan University"],
    "зкгу": ["West Kazakhstan Marat Ospanov University"],
    "пгу": ["Toraighyrov University", "Pavlodar State University"],
    "кызму": ["Korkyt Ata Kyzylorda University"],
    "атырау": ["Atyrau University"],
    "актобе": ["Aktobe Regional University"],
    "тараз": ["Taraz Regional University"],
    "семей": ["Shakarim University", "Semey Medical University"],
    "костанай": ["Kostanay Regional University"],
    "туран": ["Turan University"],
    "алматы": ["Almaty Management University"],
    "алмау": ["Almaty Management University", "AlmaU"],
    "almau": ["Almaty Management University"],
    "мук": ["International University of Information Technologies", "IITU"],
    "iitu": ["International University of Information Technologies"],
    "мниу": ["Maqsut Narikbayev University", "KAZGUU"],
    "казгюу": ["Maqsut Narikbayev University", "KAZGUU University"],
    "kazguu": ["Maqsut Narikbayev University"],
    "каспийский": ["Caspian University"],
    "жубанов": ["Zhubanov University"],
    "букетов": ["Karaganda Buketov University"],
    "торайгыров": ["Toraighyrov University"],
}


def normalize(text: str) -> str:
    """Каноничный вид строки: нижний регистр, без пунктуации и лишних пробелов."""
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    text = re.sub(r"[^\w\s\-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"[\s\-_]+", " ", text)
    return text.strip()


def translit_cyr_to_lat(text: str) -> str:
    return "".join(_CYR2LAT.get(ch, ch) for ch in text.lower())


def translit_lat_to_cyr(text: str) -> str:
    return "".join(_LAT2CYR.get(ch, ch) for ch in text.lower())


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def expand_query(query: str) -> list[str]:
    """Варианты запроса для параллельного поиска по Wikidata.

    Порядок важен: первым идёт исходный запрос, дальше — расширения.
    """
    q = query.strip()
    norm = normalize(q)
    variants: list[str] = [q]

    for token_key in (norm, norm.replace(" ", "")):
        for extra in ABBREVIATIONS.get(token_key, []):
            if extra not in variants:
                variants.append(extra)

    if _has_cyrillic(norm):
        lat = translit_cyr_to_lat(norm)
        if lat and lat not in variants:
            variants.append(lat)
    else:
        # Короткое латинское слово — вероятно аббревиатура, набранная не в той раскладке.
        if len(norm) <= 8 and " " not in norm:
            cyr = translit_lat_to_cyr(norm)
            if cyr and cyr not in variants:
                variants.append(cyr)

    return variants[:5]


def similarity(query: str, *candidates: str | None) -> float:
    """0..1 — максимальное нечёткое совпадение запроса с названием/алиасами."""
    q = normalize(query)
    q_lat = translit_cyr_to_lat(q)
    best = 0.0
    for cand in candidates:
        if not cand:
            continue
        c = normalize(cand)
        for a, b in ((q, c), (q_lat, translit_cyr_to_lat(c))):
            best = max(
                best,
                fuzz.token_set_ratio(a, b) / 100.0,
                fuzz.partial_ratio(a, b) / 100.0 * 0.95,
            )
        # Аббревиатура против первых букв слов: "kbtu" ~ "kazakh british technical university"
        initials = "".join(w[0] for w in c.split() if w)
        if len(q) >= 2 and initials:
            best = max(best, fuzz.ratio(q.replace(" ", ""), initials) / 100.0)
            best = max(best, fuzz.ratio(q_lat.replace(" ", ""), initials) / 100.0)
    return round(min(best, 1.0), 4)
