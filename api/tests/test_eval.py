"""Сам замер точности тоже проверяем: цифры не должны врать."""
import json
from pathlib import Path

from eval.metrics import Score, binary_score, macro_f1, per_class
from eval.run_eval import DEFAULT_DATASET, evaluate


def test_precision_recall_math():
    # 2 верных попадания, 1 ложное, 1 пропущенное
    score = binary_score([(True, True), (True, True), (True, False), (False, True)])
    assert score.tp == 2 and score.fp == 1 and score.fn == 1
    assert score.precision == 2 / 3
    assert score.recall == 2 / 3
    assert round(score.f1, 4) == round(2 / 3, 4)


def test_empty_score_does_not_divide_by_zero():
    empty = Score()
    assert empty.precision == 0.0 and empty.recall == 0.0 and empty.f1 == 0.0


def test_per_class_counts_each_class_separately():
    scores = per_class([("campus", "campus"), ("campus", "dorms"), ("labs", "labs")])
    assert scores["campus"].tp == 1 and scores["campus"].fp == 1
    assert scores["dorms"].fn == 1
    assert scores["labs"].f1 == 1.0
    # Классы без примеров не тянут macro-F1 вниз.
    assert 0 < macro_f1(scores) <= 1


def test_dataset_is_fully_labeled():
    data = json.loads(Path(DEFAULT_DATASET).read_text(encoding="utf-8"))
    assert len(data["items"]) >= 10
    for item in data["items"]:
        assert isinstance(item["expected_keep"], bool), item["title"]
        assert item["expected_category"], item["title"]


def test_eval_runs_and_keeps_quality_above_the_bar():
    """Порог в тесте: если правки уронят точность, сборка это заметит."""
    data = json.loads(Path(DEFAULT_DATASET).read_text(encoding="utf-8"))
    report = evaluate(data)

    assert report["keep"]["precision"] >= 0.95, "чужие фото не должны попадать в выдачу"
    assert report["keep"]["recall"] >= 0.90, "подходящие фото не должны теряться"
    assert report["macro_f1"] >= 0.85
