import datetime as dt

import pytest

from app.coerce import coerce_dict, coerce_value, derive_age


def test_numeric_strings_become_numbers():
    assert coerce_value("age", "62") == 62
    assert coerce_value("land_holding", "1.5") == 1.5
    assert coerce_value("income_amount", "1,20,000") == 120000


def test_bad_number_raises():
    with pytest.raises(ValueError):
        coerce_value("age", "sixty")


def test_text_fields_normalised():
    assert coerce_value("gender", "Female") == "female"
    assert coerce_value("gender", "F") == "female"
    assert coerce_value("income_band", "bpl") == "BPL"
    assert coerce_value("occupation", " Farmer ") == "farmer"


def test_coerce_dict_drops_unusable_numbers():
    assert coerce_dict({"age": "abc", "gender": "Male"}) == {"gender": "male"}


def test_derive_age_formats_and_birthday_boundary():
    today = dt.date(2026, 10, 10)
    assert derive_age("10-10-1966", today) == 60       # birthday today
    assert derive_age("11-10-1966", today) == 59       # birthday tomorrow
    assert derive_age("1966-10-10", today) == 60
    assert derive_age("not a date", today) is None
    assert derive_age("31-02-1990", today) is None
