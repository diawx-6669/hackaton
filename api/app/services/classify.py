"""Классификация фото по категориям — по метаданным Commons.

Это НЕ CLIP (шаг 5 ТЗ) и мы этого не скрываем: классификатор читает реальные
данные файла — имя, подпись, категории Commons — и ищет в них признаки
категории. Уверенность такого метода ограничена сверху (0.85), в UI и в
уликах он подписан как «по метаданным». Когда появится CLIP zero-shot,
он станет вторым, более сильным сигналом, а этот останется как дешёвый
предварительный фильтр для отсева явного мусора.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.models import Photo, PhotoCategory

# Термины намеренно на ru/en/kk — Commons описывают на всех трёх.
CATEGORY_TERMS: dict[PhotoCategory, tuple[str, ...]] = {
    PhotoCategory.DORMS: (
        "dormitor", "dorm ", "hostel", "residence hall", "student housing",
        "общежит", "жатақхана", "студенческий дом",
    ),
    PhotoCategory.LIBRARIES: (
        "library", "librar", "reading room", "библиотек", "кітапхана", "читальн",
    ),
    PhotoCategory.LABS: (
        "laborator", "lab ", "research center", "research centre", "workshop",
        "лаборатор", "зертхана", "научн", "исследовательск",
    ),
    PhotoCategory.SPORTS: (
        "sport", "gym", "stadium", "swimming pool", "football", "basketball",
        "volleyball", "athletic", "fitness", "спорт", "стадион", "бассейн",
        "спортзал", "дене шынықтыру", "манеж",
    ),
    PhotoCategory.CLASSROOMS: (
        "classroom", "lecture hall", "lecture room", "auditorium", "aula",
        "seminar room", "аудитор", "лекцион", "дәрісхана", "учебн", "класс",
    ),
    PhotoCategory.STUDENT_LIFE: (
        "student", "graduation", "commencement", "ceremony", "festival",
        "concert", "conference", "club", "volunteer", "студент", "студенч",
        "выпускн", "праздн", "фестивал", "конкурс", "церемон", "оқушы",
    ),
    PhotoCategory.CAMPUS: (
        "campus", "building", "faculty", "entrance", "courtyard", "facade",
        "block", "hall", "кампус", "корпус", "здание", "факультет", "вход",
        "двор", "фасад", "ректорат", "университет", "universitet", "институт",
    ),
    PhotoCategory.CITY: (
        "city", "street", "avenue", "square", "park", "panorama", "skyline",
        "view of", "district", "город", "улиц", "проспект", "площад", "парк",
        "панорам", "вид на", "район", "қала",
    ),
}

# Явный мусор: логотипы, схемы, документы, портреты, скриншоты (п.4 ТЗ).
JUNK_TERMS: tuple[str, ...] = (
    "logo", "coat of arms", "emblem", "seal of", "crest", "wordmark",
    "map of", "map,", " map", "plan of", "floor plan", "scheme", "diagram",
    "chart", "graph of", "infographic", "poster", "banner", "flyer",
    "certificate", "diploma", "document", "letterhead", "screenshot",
    "signature", "stamp", "postage", "banknote", "portrait of", "headshot",
    "логотип", "эмблем", "герб", "карта", "схем", "план ", "диаграмм",
    "плакат", "афиш", "документ", "диплом", "сертификат", "скриншот",
    "портрет", "подпись", "печать", "марка",
)

# Порядок разбора: специфичное раньше общего, иначе всё утонет в «кампусе».
PRIORITY: tuple[PhotoCategory, ...] = (
    PhotoCategory.DORMS,
    PhotoCategory.LIBRARIES,
    PhotoCategory.LABS,
    PhotoCategory.SPORTS,
    PhotoCategory.CLASSROOMS,
    PhotoCategory.STUDENT_LIFE,
    PhotoCategory.CAMPUS,
    PhotoCategory.CITY,
)

# Вес поля: имя файла врёт реже, чем свободное описание.
FIELD_WEIGHTS = {"title": 1.0, "categories": 0.85, "description": 0.6}

MAX_CONFIDENCE = 0.85  # эвристика по метаданным не может быть уверена полностью
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass
class Classification:
    category: PhotoCategory
    confidence: float
    matched: list[str] = field(default_factory=list)
    is_junk: bool = False


def _hits(terms: Iterable[str], fields: dict[str, str]) -> tuple[float, list[str]]:
    score = 0.0
    matched: list[str] = []
    for term in terms:
        for field_name, text in fields.items():
            if term in text:
                score += FIELD_WEIGHTS[field_name]
                matched.append(term.strip())
                break  # один термин считаем один раз, по самому весомому полю
    return score, matched


def classify(photo: Photo) -> Classification:
    """Определяет категорию фото по его метаданным Commons."""
    fields = {
        "title": photo.title.lower().replace("_", " "),
        "categories": " ".join(photo.commons_categories).lower(),
        "description": (photo.description or "").lower(),
    }

    junk_score, junk_matched = _hits(JUNK_TERMS, fields)
    if junk_score >= 1.0:
        return Classification(
            category=PhotoCategory.JUNK,
            confidence=min(MAX_CONFIDENCE, 0.45 + 0.15 * junk_score),
            matched=junk_matched[:4],
            is_junk=True,
        )

    best: Classification | None = None
    for category in PRIORITY:
        score, matched = _hits(CATEGORY_TERMS[category], fields)
        if score <= 0:
            continue
        candidate = Classification(
            category=category,
            confidence=min(MAX_CONFIDENCE, 0.35 + 0.18 * score),
            matched=matched[:4],
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate
        # Специфичная категория выигрывает у общей при сопоставимой силе.
        if best.category in (PhotoCategory.CAMPUS, PhotoCategory.CITY) and category not in (
            PhotoCategory.CAMPUS,
            PhotoCategory.CITY,
        ):
            best = candidate

    if best is None:
        return Classification(category=PhotoCategory.UNKNOWN, confidence=0.0)
    return best


def mentions_university(text: str, names: Iterable[str]) -> list[str]:
    """Ищет упоминание вуза в метаданных файла (улика из п.5 ТЗ).

    Считаем совпадением либо длинное название целиком, либо аббревиатуру
    как отдельное слово — чтобы «KBTU» не ловилось внутри случайных строк.
    """
    blob = text.lower()
    words = set(_WORD_RE.findall(blob))
    found: list[str] = []
    for name in names:
        n = (name or "").strip().lower()
        if len(n) < 3:
            continue
        if " " in n:
            if n in blob:
                found.append(name)
        elif n in words:
            found.append(name)
    return found
