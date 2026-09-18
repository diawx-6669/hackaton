"""Стоимость жизни — дословные цитаты с официального сайта вуза.

Команда предлагала «калькулятор выживания»: средний чек в столовой, цена
кофе, аренда однушки, проездной. Посчитать это честно нельзя — открытого
проверяемого источника таких цен нет, и любая цифра была бы выдумана либо
взята с одного случайного сайта и выдана за средний чек.

Что сделать можно: если вуз сам публикует цены у себя на сайте, показать эту
строчку дословно и со ссылкой на страницу. Ничего не пересчитываем, не
усредняем и не переводим в другую валюту — иначе это перестанет быть цитатой.
Не нашли — так и пишем.
"""
from __future__ import annotations

import re

from app.models import CostQuote, Costs, SiteText

# Валюты стран, вузы которых реально попадают в выдачу. Сумма должна стоять
# рядом с валютой — «стоимость указана на сайте» без числа нам не нужна.
_AMOUNT = r"\d[\d\s  .,]{2,}"
_CURRENCY = (
    r"(?:тенге|тг\.?|₸|KZT|руб(?:лей|ля|\.)?|₽|RUB|сом|сум|UZS|₴|грн|"
    r"\$|USD|долл(?:ара|аров)?|€|EUR|евро)"
)
MONEY_RE = re.compile(rf"{_AMOUNT}\s*{_CURRENCY}|{_CURRENCY}\s*{_AMOUNT}", re.IGNORECASE)

# Темы, ради которых мы вообще смотрим на цену. Всё остальное (зарплаты,
# гранты, бюджет вуза) к стоимости жизни студента отношения не имеет.
TOPICS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("housing", "Общежитие и проживание", (
        "общежит", "проживан", "жатақхана", "койко-мест", "комнат",
    )),
    ("food", "Питание", (
        "питани", "столов", "обед", "буфет", "асхана",
    )),
    ("tuition", "Обучение", (
        "обучени", "оплата за", "стоимость обучения", "контракт", "оқу ақысы",
    )),
    ("transport", "Транспорт", (
        "проездн", "транспорт", "автобус",
    )),
)

_SENTENCE_RE = re.compile(r"[^.!?\n]{10,300}[.!?]?")
MAX_QUOTES_PER_TOPIC = 2


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_costs(site_texts: list[SiteText] | None) -> Costs:
    """Цитаты с ценами. Только дословно и только с указанием страницы."""
    if not site_texts:
        return Costs(
            quotes=[],
            available=False,
            note="Текст с официального сайта не собран — цитировать нечего",
        )

    quotes: list[CostQuote] = []
    per_topic: dict[str, int] = {}
    seen: set[str] = set()

    def add(text: str, site: SiteText) -> None:
        """Кладёт цитату, если в ней есть и сумма, и тема, и место ещё осталось."""
        text = _clean(text)
        if not text or not MONEY_RE.search(text):
            return
        lower = text.lower()
        for key, title, terms in TOPICS:
            if not any(t in lower for t in terms):
                continue
            if per_topic.get(key, 0) >= MAX_QUOTES_PER_TOPIC or text in seen:
                return
            seen.add(text)
            per_topic[key] = per_topic.get(key, 0) + 1
            quotes.append(
                CostQuote(
                    topic=key,
                    topic_title=title,
                    quote=text,
                    page_title=site.title,
                    url=site.url,
                )
            )
            return

    for site in site_texts:
        # 1. Таблицы. Цены на сайтах вузов почти всегда таблицей, и тогда тема
        # («Проживание») стоит в одной ячейке, а сумма — в соседней. Поэтому
        # смотрим и саму строку, и её пару с предыдущей.
        previous = ""
        for row in site.rows:
            add(row, site)
            if previous:
                add(f"{previous} — {row}", site)
            previous = row

        # 2. Обычный текст абзацами.
        for raw in _SENTENCE_RE.findall(site.text):
            add(raw, site)

    if not quotes:
        return Costs(
            quotes=[],
            available=False,
            note=(
                "Вуз не публикует цены на страницах, которые мы обошли. "
                "Брать их со сторонних сайтов и выдавать за официальные мы не будем"
            ),
        )
    return Costs(quotes=quotes, available=True)
