"""Pydantic-схемы ответов API."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class Coordinates(BaseModel):
    lat: float
    lon: float


class University(BaseModel):
    """Вуз, найденный в Wikidata."""

    id: str = Field(..., description="Wikidata QID, например Q1798175")
    name: str
    description: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    city: Optional[str] = None
    country: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    website: Optional[str] = None
    commons_category: Optional[str] = Field(
        default=None, description="Категория Wikimedia Commons (P373)"
    )
    logo_url: Optional[str] = None
    inception: Optional[str] = None
    wikidata_url: str
    match_score: float = Field(
        default=0.0, description="0..1 — насколько запрос похож на название/алиас"
    )


class ResolveResponse(BaseModel):
    query: str
    # ambiguous=True → фронт показывает список для выбора (п.1 ТЗ)
    ambiguous: bool
    candidates: list[University]
    took_ms: int


class SourceKind(str, Enum):
    COMMONS_CATEGORY = "commons_category"
    COMMONS_GEOSEARCH = "commons_geosearch"
    COMMONS_SEARCH = "commons_search"
    OFFICIAL_SITE = "official_site"
    WEB_SEARCH = "web_search"


class PhotoCategory(str, Enum):
    CAMPUS = "campus"
    DORMS = "dorms"
    CLASSROOMS = "classrooms"
    LIBRARIES = "libraries"
    LABS = "labs"
    SPORTS = "sports"
    STUDENT_LIFE = "student_life"
    CITY = "city"
    JUNK = "junk"
    UNKNOWN = "unknown"


class RejectReason(str, Enum):
    NOT_THIS_UNIVERSITY = "not_this_university"
    NOT_A_PHOTO = "not_a_photo"
    STOCK_DOMAIN = "stock_domain"
    DUPLICATE = "duplicate"
    TOO_FAR = "too_far"
    NO_LICENSE = "no_license"
    JUNK_CLASS = "junk_class"
    LOW_CONFIDENCE = "low_confidence"
    TOO_SMALL = "too_small"


class EvidenceSignal(BaseModel):
    """Одна улика с её вкладом в итоговый балл — показывается в карточке фото."""

    key: str
    label: str
    value: float = Field(..., description="0..1 — сила улики")
    weight: float = Field(..., description="вес улики в итоговой сумме")
    detail: str


class Evidence(BaseModel):
    """Улики, из которых складывается Confidence Score (п.6 ТЗ)."""

    signals: list[EvidenceSignal] = Field(default_factory=list)

    geo_distance_m: Optional[float] = Field(
        default=None, description="Расстояние геотега фото до координат кампуса, метры"
    )
    domain_trust: float = Field(
        default=0.0, description="0..1 — доверие к домену-источнику"
    )
    domain: Optional[str] = None
    source_count: int = Field(default=1, description="В скольких источниках встретилось фото")
    name_mentions: list[str] = Field(
        default_factory=list, description="Названия вуза, найденные в метаданных файла"
    )
    age_years: Optional[float] = Field(default=None, description="Возраст снимка в годах")
    classifier_confidence: Optional[float] = Field(
        default=None, description="Уверенность zero-shot классификатора (шаг 5)"
    )
    has_license: bool = False
    license_name: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class Photo(BaseModel):
    id: str = Field(..., description="Стабильный id (нормализованное имя файла)")
    title: str
    url: str
    thumb_url: Optional[str] = None
    source_page_url: str = Field(..., description="Кликабельная страница-источник")
    source_kinds: list[SourceKind] = Field(default_factory=list)
    author: Optional[str] = None
    license: Optional[str] = None
    license_url: Optional[str] = None
    date: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime: Optional[str] = None
    description: Optional[str] = None
    commons_categories: list[str] = Field(default_factory=list)
    category: PhotoCategory = PhotoCategory.UNKNOWN
    category_source: Optional[str] = Field(
        default=None, description="Чем определена категория: metadata | clip"
    )
    category_terms: list[str] = Field(
        default_factory=list, description="Слова, по которым сработал классификатор"
    )
    stale: bool = Field(default=False, description="Снимку больше 5 лет — может быть устаревшим")
    confidence: float = 0.0
    evidence: Evidence = Field(default_factory=Evidence)
    phash: Optional[str] = None
    duplicate_of: Optional[str] = None
    reject_reason: Optional[RejectReason] = None
    reject_detail: Optional[str] = None


class Stage(str, Enum):
    RESOLVED = "resolved"
    COLLECTING = "collecting"
    FOUND = "found"
    DEDUPED = "deduped"
    CLASSIFIED = "classified"
    REJECTED = "rejected"
    VERIFIED = "verified"
    DESCRIBED = "described"
    DONE = "done"
    ERROR = "error"


class StageEvent(BaseModel):
    """Один кадр живой воронки, уходит клиенту по SSE."""

    stage: Stage
    message: str
    elapsed_ms: int
    counts: dict[str, int] = Field(default_factory=dict)
    payload: Optional[dict[str, Any]] = None


class CategoryBucket(BaseModel):
    category: PhotoCategory
    photos: list[Photo]
    # Честный флаг: подтверждённых фото в категории нет (п.6 ТЗ)
    empty_reason: Optional[str] = None


class DescriptionClaim(BaseModel):
    claim: str
    source_id: str
    url: str


class CampusDescription(BaseModel):
    """Описание кампуса, написанное LLM строго по найденным источникам."""

    summary: str
    claims: list[DescriptionClaim] = Field(default_factory=list)
    sources: list[dict[str, str]] = Field(default_factory=list)
    insufficient_data: bool = False
    # Утверждения, сославшиеся на несуществующий источник, — мы их не показываем,
    # но честно сообщаем, что они были.
    unverified_claims: list[str] = Field(default_factory=list)
    model: str = ""


class Profile(BaseModel):
    university: University
    verified: list[Photo]
    needs_review: list[Photo] = Field(
        default_factory=list, description="Низкий Confidence Score → «⚠️ Требует проверки»"
    )
    rejected: list[Photo] = Field(default_factory=list)
    by_category: list[CategoryBucket] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    description: Optional[CampusDescription] = None
    warnings: list[str] = Field(default_factory=list)
    took_ms: int = 0


class ComparisonRow(BaseModel):
    """Одна строка таблицы сравнения двух вузов."""

    key: str
    label: str
    a: str
    b: str
    winner: Optional[Literal["a", "b", "tie"]] = None


class Comparison(BaseModel):
    a: Profile
    b: Profile
    rows: list[ComparisonRow] = Field(default_factory=list)
    took_ms: int = 0


class SubscribeRequest(BaseModel):
    """Заявка «не нашли свой вуз — сообщите, когда соберём»."""

    email: EmailStr
    university: str = Field(..., min_length=2, max_length=200)
    comment: Optional[str] = Field(default=None, max_length=500)


class SubscribeResponse(BaseModel):
    ok: bool
    message: str
    # Честно говорим, уйдёт ли письмо на самом деле.
    delivery: Literal["queued", "stored_only"]
    queue_size: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    cache: dict[str, int] = Field(default_factory=dict)
