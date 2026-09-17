"""Замер точности классификатора и правил отбора (п.10 ТЗ).

Что меряем:
  1) решение «показывать / отклонить» — precision, recall, F1;
  2) отнесение к категории кампуса — precision, recall, F1 по каждому классу
     и macro-F1.

Запуск на контрольном наборе:
    python -m eval.run_eval

Собрать шаблон для разметки настоящих файлов Commons:
    python -m eval.run_eval --template Q1798175 > eval/real.json
    # проставить expected_keep и expected_category руками
    python -m eval.run_eval --dataset eval/real.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Coordinates, Photo, PhotoCategory, SourceKind  # noqa: E402
from app.services import evidence  # noqa: E402
from app.services.classify import classify  # noqa: E402
from eval.metrics import binary_score, macro_f1, per_class  # noqa: E402

DEFAULT_DATASET = Path(__file__).parent / "dataset.json"


def to_photo(item: dict) -> Photo:
    coords = item.get("coordinates")
    return Photo(
        id=item["title"].lower().replace(" ", "_"),
        title=item["title"],
        url=f"https://upload.wikimedia.org/{item['title']}",
        source_page_url=item.get(
            "source_page_url",
            f"https://commons.wikimedia.org/wiki/File:{item['title'].replace(' ', '_')}",
        ),
        source_kinds=[SourceKind(k) for k in item.get("source_kinds", ["commons_category"])],
        description=item.get("description") or None,
        commons_categories=item.get("commons_categories", []),
        coordinates=Coordinates(**coords) if coords else None,
        license=item.get("license"),
        date=item.get("date"),
        mime=item.get("mime", "image/jpeg"),
        width=item.get("width", 1600),
        height=item.get("height", 1200),
    )


def evaluate(data: dict) -> dict:
    uni = data["university"]
    campus = Coordinates(**uni["coordinates"]) if uni.get("coordinates") else None
    names = [uni["name"], *uni.get("aliases", [])]

    keep_pairs: list[tuple[bool, bool]] = []
    category_pairs: list[tuple[str, str]] = []
    mistakes: list[dict] = []

    for item in data["items"]:
        photo = to_photo(item)

        # Тот же порядок, что и в конвейере: сначала мусор по типу файла…
        if photo.mime and not photo.mime.startswith("image/") or photo.url.lower().endswith(".svg"):
            photo.category = PhotoCategory.JUNK
        else:
            result = classify(photo)
            if result.category is not PhotoCategory.UNKNOWN:
                photo.category = result.category
                photo.category_source = "metadata"
                photo.category_terms = result.matched
                photo.evidence.classifier_confidence = result.confidence

        evidence.score_photo(photo, campus, uni.get("website"), names)

        predicted_keep = evidence.bucket(photo) != "rejected"
        actual_keep = bool(item["expected_keep"])
        keep_pairs.append((predicted_keep, actual_keep))
        category_pairs.append((photo.category.value, item["expected_category"]))

        if predicted_keep != actual_keep or photo.category.value != item["expected_category"]:
            mistakes.append({
                "title": item["title"],
                "ожидали": {"показать": actual_keep, "категория": item["expected_category"]},
                "получили": {
                    "показать": predicted_keep,
                    "категория": photo.category.value,
                    "балл": photo.confidence,
                    "причина_отказа": photo.reject_reason.value if photo.reject_reason else None,
                },
            })

    keep = binary_score(keep_pairs)
    categories = per_class(category_pairs)
    return {
        "items": len(data["items"]),
        "keep": {"precision": keep.precision, "recall": keep.recall, "f1": keep.f1},
        "categories": {
            name: {
                "precision": s.precision,
                "recall": s.recall,
                "f1": s.f1,
                "support": s.support,
            }
            for name, s in categories.items()
            if s.support or s.fp
        },
        "macro_f1": macro_f1(categories),
        "mistakes": mistakes,
    }


def print_report(report: dict) -> None:
    pct = lambda v: f"{v * 100:5.1f}%"  # noqa: E731

    print(f"\nНабор: {report['items']} размеченных файлов\n")
    print("РЕШЕНИЕ «ПОКАЗАТЬ ИЛИ ОТКЛОНИТЬ»")
    k = report["keep"]
    print(f"  precision {pct(k['precision'])}   — из показанного столько действительно подходит")
    print(f"  recall    {pct(k['recall'])}   — из подходящего столько мы нашли")
    print(f"  F1        {pct(k['f1'])}\n")

    print("КАТЕГОРИИ КАМПУСА")
    print(f"  {'класс':<16}{'precision':>10}{'recall':>10}{'F1':>8}{'примеров':>10}")
    for name, s in sorted(report["categories"].items()):
        print(f"  {name:<16}{pct(s['precision']):>10}{pct(s['recall']):>10}{pct(s['f1']):>8}{s['support']:>10}")
    print(f"\n  macro-F1  {pct(report['macro_f1'])}\n")

    if report["mistakes"]:
        print(f"ОШИБКИ ({len(report['mistakes'])})")
        for m in report["mistakes"]:
            print(f"  · {m['title']}")
            print(f"      ожидали:  {m['ожидали']}")
            print(f"      получили: {m['получили']}")
    else:
        print("Ошибок нет.")
    print()


async def make_template(qid: str) -> dict:
    """Шаблон для разметки настоящих файлов: запускает конвейер и выгружает найденное."""
    from app.pipeline import build_profile

    profile, last = await build_profile(qid=qid)
    if profile is None:
        raise SystemExit(f"Профиль не собран: {last.message}")

    uni = profile.university
    items = []
    for photo in [*profile.verified, *profile.needs_review, *profile.rejected]:
        items.append({
            "title": photo.title,
            "description": photo.description or "",
            "commons_categories": photo.commons_categories,
            "source_kinds": [k.value for k in photo.source_kinds],
            "coordinates": photo.coordinates.model_dump() if photo.coordinates else None,
            "license": photo.license,
            "date": photo.date,
            "mime": photo.mime,
            "expected_keep": None,
            "expected_category": None,
        })

    return {
        "_readme": "Проставьте expected_keep (true/false) и expected_category руками.",
        "university": {
            "name": uni.name,
            "aliases": uni.aliases,
            "coordinates": uni.coordinates.model_dump() if uni.coordinates else None,
            "website": uni.website,
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Замер точности CampusLens")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--template", metavar="QID", help="выгрузить шаблон для разметки")
    parser.add_argument("--json", action="store_true", help="вывести отчёт как JSON")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(asyncio.run(make_template(args.template)), ensure_ascii=False, indent=1))
        return

    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    unlabeled = [i["title"] for i in data["items"] if i.get("expected_keep") is None]
    if unlabeled:
        raise SystemExit(f"Не размечено записей: {len(unlabeled)}. Первая: {unlabeled[0]}")

    report = evaluate(data)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
