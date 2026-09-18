"""Цены: только дословные цитаты с сайта вуза, ничего усреднённого."""
from app.models import SiteText
from app.services import costs


def site(text: str, url: str = "https://kbtu.edu.kz/ru/dorm", title: str = "Общежитие"):
    return SiteText(url=url, title=title, text=text)


def test_quotes_price_lines_with_source():
    result = costs.extract_costs([
        site("Стоимость проживания в общежитии составляет 45 000 тенге в месяц."),
        site(
            "Обед в студенческой столовой стоит в среднем 1200 тг.",
            url="https://kbtu.edu.kz/ru/food",
            title="Питание",
        ),
    ])

    assert result.available is True
    topics = {q.topic for q in result.quotes}
    assert topics == {"housing", "food"}

    housing = next(q for q in result.quotes if q.topic == "housing")
    # Цитата дословная: ни пересчёта, ни округления, ни «в среднем по городу».
    assert "45 000 тенге" in housing.quote
    assert housing.url.endswith("/dorm")
    assert housing.page_title == "Общежитие"


def test_sentence_without_amount_is_not_a_price():
    result = costs.extract_costs([site("Стоимость проживания уточняйте в деканате.")])
    assert result.available is False
    assert result.quotes == []


def test_amount_without_cost_topic_is_ignored():
    """4000 студентов — это не цена, хотя число рядом с текстом есть."""
    result = costs.extract_costs([site("В университете учится 4000 студентов.")])
    assert result.quotes == []


def test_no_site_text_says_so_plainly():
    result = costs.extract_costs([])
    assert result.available is False
    assert result.note and "не собран" in result.note


def test_nothing_found_refuses_to_guess():
    result = costs.extract_costs([site("Университет основан в 2001 году.")])
    assert result.available is False
    assert result.note and "сторонних" in result.note


def test_same_sentence_not_duplicated():
    line = "Проживание в общежитии — 45 000 тенге."
    result = costs.extract_costs([site(line), site(line, url="https://kbtu.edu.kz/ru/other")])
    assert len(result.quotes) == 1


def test_at_most_two_quotes_per_topic():
    text = " ".join(
        f"Проживание в общежитии стоит {n} 000 тенге." for n in range(40, 45)
    )
    result = costs.extract_costs([site(text)])
    assert len([q for q in result.quotes if q.topic == "housing"]) == 2


def test_price_from_table_cells():
    """Цены почти всегда в таблице: тема в одной ячейке, сумма в соседней."""
    result = costs.extract_costs([
        SiteText(
            url="https://kbtu.edu.kz/ru/dorm",
            title="Общежитие",
            text="",
            rows=["Услуга", "Стоимость", "Проживание в общежитии", "45 000 тенге в месяц"],
        )
    ])

    assert result.available is True
    quote = result.quotes[0]
    assert "Проживание в общежитии" in quote.quote
    assert "45 000 тенге" in quote.quote
    assert quote.url.endswith("/dorm")


def test_table_without_amounts_is_not_a_price():
    result = costs.extract_costs([
        SiteText(
            url="https://kbtu.edu.kz/ru/dorm",
            title="Общежитие",
            text="",
            rows=["Проживание в общежитии", "уточняйте в деканате"],
        )
    ])
    assert result.available is False
