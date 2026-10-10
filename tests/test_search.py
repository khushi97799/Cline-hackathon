"""Search: works from one letter, forgives typos, understands Hinglish/Hindi, ranks sensibly."""
import pytest

from app.fuzzy import edit_distance, word_score, words
from app.search import search, suggest
from app.tag_labels import TAG_LABELS


def card(sid, name, benefit, tags, category="x"):
    return {"scheme_id": sid, "name": name, "benefit": benefit, "tags": tags, "category": category, "level": "central", "state": "ALL"}


CARDS = [
    card("pm-kisan", "PM-KISAN", "Rs. 6,000 per year in three installments of Rs. 2,000", ["farmer"], "agriculture"),
    card("pm-ujjwala", "PM Ujjwala Yojana", "Free LPG connection with first refill and stove assistance", ["women", "energy"], "household"),
    card("nsap", "NSAP - Old Age Pension (IGNOAPS)", "Monthly pension paid to bank or post office account", ["senior", "pension"], "pension"),
]


def ids(q):
    return [c["scheme_id"] for c in search(CARDS, q, TAG_LABELS)]


@pytest.mark.parametrize("q,first", [
    ("k", "pm-kisan"), ("ki", "pm-kisan"), ("kis", "pm-kisan"), ("u", "pm-ujjwala"), ("uj", "pm-ujjwala"),
    ("p", None), ("pen", "nsap"), ("old", "nsap"), ("lpg", "pm-ujjwala"), ("gas", "pm-ujjwala"),
])
def test_one_or_two_letters_already_give_suggestions(q, first):
    got = ids(q)
    assert got, f"'{q}' should find something"
    if first:
        assert got[0] == first


@pytest.mark.parametrize("q,expected", [
    ("kisaan", "pm-kisan"), ("kissan", "pm-kisan"), ("pension", "nsap"), ("pansion", "nsap"), ("ujwala", "pm-ujjwala"),
    ("ujjwla", "pm-ujjwala"), ("pensoin", "nsap"), ("farmar", "pm-kisan"),
])
def test_typos_are_forgiven(q, expected):
    assert ids(q)[0] == expected


@pytest.mark.parametrize("q,expected", [
    ("kheti", "pm-kisan"), ("kisan", "pm-kisan"), ("किसान", "pm-kisan"), ("खेती", "pm-kisan"), ("mahila", "pm-ujjwala"),
    ("महिला", "pm-ujjwala"), ("bujurg", "nsap"), ("बुजुर्ग", "nsap"), ("budhapa", "nsap"), ("वृद्ध", "nsap"),
    ("cylinder", "pm-ujjwala"), ("रसोई", "pm-ujjwala"), ("पेंशन", "nsap"), ("farmers", "pm-kisan"),
])
def test_everyday_words_in_hinglish_and_hindi_find_the_right_scheme(q, expected):
    assert ids(q)[0] == expected


def test_every_typed_word_must_match():
    assert ids("women pension") == []                        # no scheme is both
    assert ids("old age pension") == ["nsap"]
    assert ids("zzzz") == [] and ids("xq") == []
    assert ids("   ") == [c["scheme_id"] for c in CARDS]     # an empty search shows everything


def test_names_rank_above_descriptions():
    cards = [card("a", "Bank Helper", "pension for everyone", ["pension"]), card("b", "Pension Plus", "monthly money", ["senior"])]
    assert [c["scheme_id"] for c in search(cards, "pension", TAG_LABELS)] == ["b", "a"]


def test_short_words_are_not_matched_loosely():
    assert word_score("ab", ["abc"]) > 0          # a prefix is fine
    assert word_score("xyz", ["abc"]) == 0        # but unrelated short words never match by "typo"
    assert edit_distance("kisan", "kisaan", 2) == 1
    assert words("PM-KISAN  (IGNOAPS)") == ["pm", "kisan", "ignoaps"]


def test_suggestions_explain_why_they_matched():
    s = suggest(CARDS, "kis", TAG_LABELS)
    assert s[0]["scheme_id"] == "pm-kisan" and s[0]["match"] == "name"
    by_tag = suggest(CARDS, "kheti", TAG_LABELS)
    assert by_tag[0]["match"] == "tag"
    assert suggest(CARDS, "", TAG_LABELS)[0]["scheme_id"] == "pm-kisan"          # empty -> first few schemes
    assert len(suggest(CARDS, "p", TAG_LABELS, limit=2)) <= 2


def test_search_api_and_suggest_endpoint(client):
    r = client.get("/api/schemes/suggest?q=k").json()["suggestions"]
    assert r and r[0]["scheme_id"] == "pm-kisan"
    assert client.get("/api/schemes/suggest?q=zzzzzz").json()["suggestions"] == []
    assert client.get("/api/schemes?q=kisaan").json()["schemes"][0]["scheme_id"] == "pm-kisan"
    both = client.get("/api/schemes?q=kheti&level=central").json()["schemes"]
    assert [s["scheme_id"] for s in both] == ["pm-kisan"]
    assert client.get("/api/schemes?q=pension&tag=farmer").json()["schemes"] == []     # filters and search combine
    assert len(client.get("/api/schemes/suggest?q=" + "a" * 500).json()["suggestions"]) <= 6
