"""Precision, recall и F1 — без внешних зависимостей."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        """Из того, что мы показали, сколько действительно подходит."""
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        """Из того, что должно было попасть, сколько мы нашли."""
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def support(self) -> int:
        return self.tp + self.fn


def binary_score(pairs: list[tuple[bool, bool]]) -> Score:
    """pairs — список (предсказано, на самом деле)."""
    score = Score()
    for predicted, actual in pairs:
        if predicted and actual:
            score.tp += 1
        elif predicted and not actual:
            score.fp += 1
        elif not predicted and actual:
            score.fn += 1
    return score


def per_class(pairs: list[tuple[str, str]]) -> dict[str, Score]:
    """pairs — список (предсказанный класс, истинный класс)."""
    classes = sorted({c for pair in pairs for c in pair})
    scores = {c: Score() for c in classes}
    for predicted, actual in pairs:
        for c in classes:
            if predicted == c and actual == c:
                scores[c].tp += 1
            elif predicted == c and actual != c:
                scores[c].fp += 1
            elif predicted != c and actual == c:
                scores[c].fn += 1
    return scores


def macro_f1(scores: dict[str, Score]) -> float:
    """Среднее F1 по классам, у которых есть примеры."""
    present = [s for s in scores.values() if s.support]
    return sum(s.f1 for s in present) / len(present) if present else 0.0
