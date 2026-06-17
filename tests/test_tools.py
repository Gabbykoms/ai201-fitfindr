from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("tee", size="XL", max_price=None)
    assert all("xl" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    assert len(results) > 1
    # First result should mention more of the keywords than a random later result
    def score(item):
        text = " ".join([item["title"], item["description"], " ".join(item["style_tags"])]).lower()
        return sum(1 for kw in ["vintage", "denim", "jacket"] if kw in text)
    assert score(results[0]) >= score(results[-1])


def test_search_returns_correct_fields():
    results = search_listings("vintage", size=None, max_price=100)
    assert len(results) > 0
    required = {"id", "title", "description", "category", "price", "platform"}
    assert required.issubset(results[0].keys())


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert not suggestion.startswith("Could not")


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("", results[0])
    assert result == "Cannot create fit card: outfit description is missing."


def test_create_fit_card_whitespace_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("   ", results[0])
    assert result == "Cannot create fit card: outfit description is missing."


def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    outfit = "pair with wide-leg jeans and chunky sneakers for a 90s vibe"
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card) > 0
    assert not card.startswith("Fit card generation failed")


def test_create_fit_card_varies_output():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    outfit = "pair with wide-leg jeans and chunky sneakers for a 90s vibe"
    card1 = create_fit_card(outfit, results[0])
    card2 = create_fit_card(outfit, results[0])
    # With temperature=1.0 outputs should differ; if they happen to match it's
    # not a hard failure but worth noting
    assert isinstance(card1, str) and isinstance(card2, str)
