"""Utilities for extracting high-signal intent from search queries."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple


# Minimal stopword list tailored for ticket phrasing
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "when",
    "this",
    "that",
    "from",
    "into",
    "have",
    "having",
    "cant",
    "can't",
    "cannot",
    "trying",
    "error",
    "issue",
    "problem",
    "access",
    "open",
    "opening",
    "launch",
    "launching",
    "login",
    "log",
    "fails",
    "failure",
    "failed",
    "please",
    "help",
}


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class QueryIntent:
    """Captures extracted tokens and metadata cues from a query or seed ticket."""

    raw_query: str
    tokens: Set[str]
    keywords: Set[str]
    category: Optional[str] = None
    subcategory: Optional[str] = None
    item: Optional[str] = None

    @property
    def has_category_path(self) -> bool:
        return any([self.category, self.subcategory, self.item])


def _normalize_token(word: str) -> str:
    return word.strip().lower()


def _iter_words(text: str) -> Iterable[str]:
    for match in _WORD_RE.finditer(text or ""):
        yield _normalize_token(match.group())


@dataclass(frozen=True)
class ResultSignals:
    token_match: bool
    category_match: bool
    keyword_hits: int


@lru_cache(maxsize=1)
def _load_known_tokens(categories_path: Path | None = None) -> Set[str]:
    """Load known product tokens from categories.json if available."""

    path = categories_path or Path("categories.json")
    tokens: Set[str] = set()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for cat, subs in data.items():
                    tokens.add(_normalize_token(cat))
                    if isinstance(subs, dict):
                        for sub, items in subs.items():
                            tokens.add(_normalize_token(sub))
                            if isinstance(items, list):
                                for item in items:
                                    tokens.add(_normalize_token(str(item)))
        except Exception:
            # Non-fatal: fall back to defaults
            tokens.clear()

    # Default seed list for common software terms if categories.json is missing/invalid
    if not tokens:
        tokens.update(
            {
                "revit",
                "bluebeam",
                "teams",
                "outlook",
                "autocad",
                "photoshop",
                "sharepoint",
                "dynamo",
                "vpn",
                "onedrive",
                "microsoft",
            }
        )
    return tokens


def _extract_keywords(words: Iterable[str]) -> Set[str]:
    keywords = {word for word in words if len(word) > 3 and word not in _STOPWORDS}
    return keywords


def extract_query_intent(
    query: str,
    *,
    seed_metadata: Optional[dict] = None,
    categories_path: Optional[Path] = None,
) -> QueryIntent:
    """Derive high-signal tokens and metadata cues from the query/seed."""

    words = list(_iter_words(query))
    known_tokens = _load_known_tokens(categories_path)
    matched_tokens = {word for word in words if word in known_tokens}
    keywords = _extract_keywords(words)

    category = None
    subcategory = None
    item = None

    if seed_metadata:
        category = _normalize_or_none(seed_metadata.get("category"))
        subcategory = _normalize_or_none(seed_metadata.get("subcategory"))
        item = _normalize_or_none(seed_metadata.get("item"))

        # Include seed tokens as matched tokens to boost re-use
        for value in (category, subcategory, item):
            if value:
                matched_tokens.add(value)

    return QueryIntent(
        raw_query=query,
        tokens=matched_tokens,
        keywords=keywords,
        category=category,
        subcategory=subcategory,
        item=item,
    )


def _normalize_or_none(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return _normalize_token(value) if value else None


def annotate_result_with_tokens(
    document_text: str,
    metadata: dict,
    intent: QueryIntent,
) -> ResultSignals:
    """Evaluate how well a result aligns with the extracted intent."""

    text_words = set(_iter_words(document_text))
    meta_tokens = {
        _normalize_or_none(metadata.get("category")),
        _normalize_or_none(metadata.get("subcategory")),
        _normalize_or_none(metadata.get("item")),
    }

    token_match = any(token in text_words or token in meta_tokens for token in intent.tokens)

    category_match = False
    if intent.category and _normalize_or_none(metadata.get("category")) == intent.category:
        category_match = True
        if intent.subcategory:
            category_match = category_match and (
                _normalize_or_none(metadata.get("subcategory")) == intent.subcategory
            )
        if intent.item:
            category_match = category_match and (
                _normalize_or_none(metadata.get("item")) == intent.item
            )

    keyword_hits = len(intent.keywords.intersection(text_words))

    return ResultSignals(token_match=token_match, category_match=category_match, keyword_hits=keyword_hits)
