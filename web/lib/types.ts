// Типы зеркалят pydantic-схемы бэкенда (api/app/models.py).

export type Coordinates = { lat: number; lon: number };

export type University = {
  id: string;
  name: string;
  description?: string | null;
  aliases: string[];
  city?: string | null;
  country?: string | null;
  coordinates?: Coordinates | null;
  website?: string | null;
  commons_category?: string | null;
  logo_url?: string | null;
  inception?: string | null;
  wikidata_url: string;
  match_score: number;
};

export type ResolveResponse = {
  query: string;
  ambiguous: boolean;
  candidates: University[];
  took_ms: number;
};

export type EvidenceSignal = {
  key: string;
  label: string;
  value: number;
  weight: number;
  detail: string;
};

export type Evidence = {
  signals: EvidenceSignal[];
  name_mentions: string[];
  age_years?: number | null;
  geo_distance_m?: number | null;
  domain_trust: number;
  domain?: string | null;
  source_count: number;
  classifier_confidence?: number | null;
  has_license: boolean;
  license_name?: string | null;
  notes: string[];
};

export type PhotoCategory =
  | "campus"
  | "dorms"
  | "classrooms"
  | "libraries"
  | "labs"
  | "sports"
  | "student_life"
  | "city"
  | "junk"
  | "unknown";

export type Photo = {
  id: string;
  title: string;
  url: string;
  thumb_url?: string | null;
  source_page_url: string;
  source_kinds: string[];
  author?: string | null;
  license?: string | null;
  license_url?: string | null;
  date?: string | null;
  coordinates?: Coordinates | null;
  width?: number | null;
  height?: number | null;
  mime?: string | null;
  description?: string | null;
  commons_categories: string[];
  category: PhotoCategory;
  category_source?: string | null;
  category_terms: string[];
  stale: boolean;
  confidence: number;
  evidence: Evidence;
  phash?: string | null;
  duplicate_of?: string | null;
  reject_reason?: string | null;
  reject_detail?: string | null;
};

export type CategoryBucket = {
  category: PhotoCategory;
  photos: Photo[];
  empty_reason?: string | null;
};

export type DescriptionClaim = {
  claim: string;
  source_id: string;
  url: string;
};

export type CampusDescription = {
  summary: string;
  claims: DescriptionClaim[];
  sources: { id: string; text: string; url: string }[];
  insufficient_data: boolean;
  unverified_claims: string[];
  model: string;
};

export type Profile = {
  university: University;
  verified: Photo[];
  needs_review: Photo[];
  rejected: Photo[];
  by_category: CategoryBucket[];
  stats: Record<string, number>;
  description?: CampusDescription | null;
  warnings: string[];
  took_ms: number;
  /** true — фото уже показаны, но конвейер ещё дописывает описание кампуса. */
  partial?: boolean;
  surroundings?: Surroundings | null;
};

export type SurroundingPlace = {
  name: string;
  distance_m: number;
  walk_minutes: number;
  osm_url: string;
};

export type SurroundingGroup = {
  key: string;
  title: string;
  count: number;
  nearest: SurroundingPlace[];
  empty_reason?: string | null;
};

export type Surroundings = {
  radius_m: number;
  groups: SurroundingGroup[];
  total: number;
  available: boolean;
  error?: string | null;
};

export type Stage =
  | "classified"
  | "described"
  | "resolved"
  | "collecting"
  | "found"
  | "deduped"
  | "rejected"
  | "verified"
  | "done"
  | "error";

export type StageEvent = {
  stage: Stage;
  message: string;
  elapsed_ms: number;
  counts: Record<string, number>;
  payload?: Record<string, unknown> | null;
};

export const CATEGORY_LABELS: Record<PhotoCategory, string> = {
  campus: "Кампус",
  dorms: "Общежития",
  classrooms: "Аудитории",
  libraries: "Библиотеки",
  labs: "Лаборатории",
  sports: "Спорт",
  student_life: "Студенческая жизнь",
  city: "Город",
  junk: "Мусор",
  unknown: "Без категории",
};

export const REJECT_LABELS: Record<string, string> = {
  not_this_university: "Не тот вуз",
  not_a_photo: "Не фотография",
  stock_domain: "Стоковый источник",
  duplicate: "Дубликат",
  too_far: "Далеко от кампуса",
  no_license: "Нет лицензии",
  junk_class: "Мусорный класс",
  low_confidence: "Низкий балл",
  too_small: "Слишком мелкое",
};

export const SOURCE_LABELS: Record<string, string> = {
  commons_category: "Категория Commons",
  commons_geosearch: "Геопоиск Commons",
  commons_search: "Поиск по названию",
  official_site: "Сайт вуза",
  web_search: "Веб-поиск",
};

export type ComparisonRow = {
  key: string;
  label: string;
  a: string;
  b: string;
  winner?: "a" | "b" | "tie" | null;
};

export type Comparison = {
  a: Profile;
  b: Profile;
  rows: ComparisonRow[];
  took_ms: number;
};

export type UploadRecord = {
  id: string;
  url: string;
  width: number;
  height: number;
  caption?: string | null;
  university_name?: string | null;
  has_geotag: boolean;
  coins: number;
  created_at: string;
};

export type Wallet = {
  photos: number;
  coins: number;
  per_photo: number;
};
