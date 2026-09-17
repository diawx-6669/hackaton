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
    city_coordinates: Optional[Coordinates] = Field(
        default=None, description="Координаты города (P131) — для расчёта пути до центра"
    )
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
    # Столовые, буфеты, кухни, прачечные — быт, о котором спрашивают чаще всего.
    FOOD = "food"
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
    stale: bool = Field(default=False, description="Снимку больше 5 лет (влияет на улику «Свежесть»)")
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


class SurroundingPlace(BaseModel):
    """Один объект рядом с кампусом по данным OpenStreetMap."""

    name: str = Field(default="", description="Название из OSM; пустое — объект без имени")
    distance_m: int = Field(..., description="Расстояние по прямой от координат кампуса")
    walk_minutes: int = Field(..., description="Оценка пешком по прямой, не по маршруту")
    osm_url: str
    coordinates: Optional[Coordinates] = None


class SurroundingGroup(BaseModel):
    key: str
    title: str
    count: int
    nearest: list[SurroundingPlace] = Field(default_factory=list)
    # Честный флаг: в OSM объектов этой группы рядом нет.
    empty_reason: Optional[str] = None


class Surroundings(BaseModel):
    """«Жизнь в радиусе 15 минут» (п.8 ТЗ) — только то, что отмечено в OSM."""

    radius_m: int
    groups: list[SurroundingGroup] = Field(default_factory=list)
    total: int = 0
    available: bool = True
    error: Optional[str] = None


class CostQuote(BaseModel):
    """Дословная строка с ценой с сайта вуза. Не пересчитана и не усреднена."""

    topic: str
    topic_title: str
    quote: str
    page_title: str
    url: str


class Costs(BaseModel):
    """Стоимость — только цитаты из официального источника (см. services/costs.py)."""

    quotes: list[CostQuote] = Field(default_factory=list)
    available: bool = False
    note: Optional[str] = None


class EventGroup(BaseModel):
    """Событие вуза, собранное из уже найденных фото — не из расписания."""

    title: str
    photo_ids: list[str] = Field(default_factory=list)
    count: int = 0
    years: list[int] = Field(
        default_factory=list, description="Годы съёмки; у файлов без даты года нет"
    )


class CampusVideo(BaseModel):
    """Видео с Wikimedia Commons. Сторонние площадки не трогаем: это их правила."""

    id: str
    title: str
    url: str
    source_page_url: str
    author: Optional[str] = None
    license: Optional[str] = None
    duration_s: Optional[int] = None
    mime: str


class DistrictInfo(BaseModel):
    """Инфраструктура района по OSM.

    Здесь намеренно нет сводного «индекса безопасности»: данных, из которых его
    можно было бы честно собрать (охрана, реальная освещённость, ночная
    обстановка), в открытых источниках нет. Есть только то, что отмечено на
    карте, — и отдельно сказано, у скольких улиц тег освещения не проставлен.
    """

    radius_m: int
    streets_total: int = 0
    streets_lit: int = 0
    streets_unlit: int = 0
    streets_without_lit_tag: int = 0
    lit_share_percent: Optional[int] = Field(
        default=None, description="Доля освещённых среди улиц С ТЕГОМ lit, не среди всех"
    )
    street_lamps: int = 0
    crossings: int = 0
    emergency_phones: int = 0
    police: Optional[SurroundingPlace] = None
    available: bool = True
    error: Optional[str] = None


class RouteLeg(BaseModel):
    """Один участок пути. Либо реальный маршрут OSRM, либо расстояние по прямой."""

    key: str
    title: str
    from_name: str
    to_name: str
    distance_m: int
    minutes: int
    mode: Literal["driving", "straight"] = "straight"
    note: str = ""


class Logistics(BaseModel):
    """Логистика: сколько добираться (п.8 ТЗ, «дорога на пары»)."""

    legs: list[RouteLeg] = Field(default_factory=list)
    available: bool = True
    error: Optional[str] = None


class Profile(BaseModel):
    university: University
    verified: list[Photo]
    needs_review: list[Photo] = Field(
        default_factory=list, description="Низкий Confidence Score → «Требует проверки»"
    )
    rejected: list[Photo] = Field(default_factory=list)
    by_category: list[CategoryBucket] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    description: Optional[CampusDescription] = None
    warnings: list[str] = Field(default_factory=list)
    took_ms: int = 0
    partial: bool = Field(
        default=False,
        description="Фото уже готовы, но конвейер ещё работает (описание кампуса впереди)",
    )
    surroundings: Optional[Surroundings] = None
    district: Optional[DistrictInfo] = None
    events: list[EventGroup] = Field(default_factory=list)
    videos: list[CampusVideo] = Field(default_factory=list)
    costs: Optional[Costs] = None
    logistics: Optional[Logistics] = None


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


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class SiteText(BaseModel):
    """Фрагмент текста со страницы официального сайта вуза."""

    url: str
    title: str
    text: str


class UploadRecord(BaseModel):
    """Фотография, загруженная студентом. Не входит в проверенную галерею."""

    id: str
    url: str
    width: int
    height: int
    caption: Optional[str] = None
    university_name: Optional[str] = None
    has_geotag: bool = False
    coins: int = 0
    created_at: str


class UploadListResponse(BaseModel):
    items: list[UploadRecord] = Field(default_factory=list)


class WalletResponse(BaseModel):
    photos: int
    coins: int
    per_photo: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    cache: dict[str, int] = Field(default_factory=dict)
