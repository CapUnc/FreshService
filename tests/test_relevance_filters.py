from search_intent import QueryIntent, ResultSignals
from search_tickets import _adjust_distance, _apply_strict_filters


def test_adjust_distance_penalizes_missing_tokens() -> None:
    intent = QueryIntent(raw_query="revit access", tokens={"revit"}, keywords={"revit", "access"})
    signals = ResultSignals(token_match=False, category_match=False, keyword_hits=0)

    dist = 0.4
    adjusted = _adjust_distance(dist, intent, signals)

    assert adjusted > dist  # penalty applied when tokens are missing


def test_adjust_distance_rewards_full_match() -> None:
    intent = QueryIntent(
        raw_query="outlook crash",
        tokens={"outlook"},
        keywords={"outlook", "crash"},
        category="software",
    )
    signals = ResultSignals(token_match=True, category_match=True, keyword_hits=2)

    dist = 0.5
    adjusted = _adjust_distance(dist, intent, signals)

    assert adjusted < dist  # bonus applied when everything matches


def test_apply_strict_filters_respects_requirements() -> None:
    intent = QueryIntent(raw_query="teams", tokens={"teams"}, keywords={"teams"})
    results = [
        ("doc1", {"relevance": {"token_match": True, "category_match": False}}, 0.2),
        ("doc2", {"relevance": {"token_match": False, "category_match": True}}, 0.25),
    ]

    token_only = _apply_strict_filters(results, intent=intent, require_token=True, require_category=False)
    assert len(token_only) == 1
    assert token_only[0][0] == "doc1"

    both = _apply_strict_filters(
        results,
        intent=intent,
        require_token=True,
        require_category=True,
    )
    # No category path in intent -> category requirement ignored, token requirement still applies
    assert len(both) == 1

