import json
from pathlib import Path

from search_intent import (
    QueryIntent,
    ResultSignals,
    annotate_result_with_tokens,
    extract_query_intent,
    _load_known_tokens,  # type: ignore[attr-defined]
)


def test_extract_query_intent_detects_known_tokens(tmp_path: Path) -> None:
    # Arrange
    categories = {"Software": {"Revit": ["Desktop"]}}
    categories_path = tmp_path / "categories.json"
    categories_path.write_text(json.dumps(categories), encoding="utf-8")

    # Act
    _load_known_tokens.cache_clear()  # type: ignore[attr-defined]
    intent = extract_query_intent(
        "Getting an access error when I open Revit",
        categories_path=categories_path,
    )

    # Assert: "revit" is a known product token. "access" is an intentional
    # stopword (see _STOPWORDS), so it must NOT appear in keywords; a genuine
    # high-signal word like "getting" should.
    assert "revit" in intent.tokens
    assert "getting" in intent.keywords
    assert "access" not in intent.keywords


def test_annotate_result_with_tokens_matches_text_and_metadata(tmp_path: Path) -> None:
    categories = {"Applications": {"Bluebeam": ["Revu"]}}
    categories_path = tmp_path / "categories.json"
    categories_path.write_text(json.dumps(categories), encoding="utf-8")

    # category_match only fires when the intent carries a category path, which
    # comes from the seeded ticket's metadata (not from free text).
    _load_known_tokens.cache_clear()  # type: ignore[attr-defined]
    intent = extract_query_intent(
        "Bluebeam crashes on launch",
        seed_metadata={"category": "Applications", "subcategory": "Bluebeam", "item": "Revu"},
        categories_path=categories_path,
    )

    metadata = {"category": "Applications", "subcategory": "Bluebeam", "item": "Revu"}
    doc = "Customer reports Bluebeam Revu crashes immediately after launch."

    signals = annotate_result_with_tokens(doc, metadata, intent)

    assert isinstance(signals, ResultSignals)
    assert signals.token_match is True
    assert signals.category_match is True
    assert signals.keyword_hits >= 1
