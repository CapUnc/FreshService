"""Helpers for assembling rich Freshservice ticket context for AI guidance."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import json
import time
import logging

from config import (
    FRESHSERVICE_BASE_URL,
    MAX_SIMILAR_TICKETS,
    RATE_LIMIT_SLEEP,
    REQUEST_TIMEOUT,
    freshservice_session,
)
from agent_resolver import get_group_name

logger = logging.getLogger(__name__)


@dataclass
class ConversationNote:
    body: str
    is_private: bool
    author: Optional[str]
    created_at: Optional[str]


@dataclass
class TicketContext:
    ticket_id: int
    subject: str
    description: str
    category: Optional[str]
    subcategory: Optional[str]
    item: Optional[str]
    group_id: Optional[int]
    group_name: Optional[str]
    responder_name: Optional[str]
    distance: float
    notes: List[ConversationNote]
    notes_incomplete: bool


@lru_cache(maxsize=1)
def load_category_tree(path: Path | str = Path("categories.json")) -> dict:
    """Load category tree with caching. Cache is cleared when path changes."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def gather_ticket_contexts(
    results: Iterable[tuple[str, dict, float]],
    *,
    limit: int | None = MAX_SIMILAR_TICKETS,
) -> List[TicketContext]:
    """Fetch enriched context for the top-N similar tickets.

    Each context bundles the public ticket fields plus private conversations so
    the guidance model can see what ultimately solved the incident. When the
    Freshservice API call fails we fall back to a lightweight version built
    from the search metadata so the downstream pipeline keeps running.
    The limit is capped by MAX_SIMILAR_TICKETS to avoid excessive token usage.
    
    Uses parallel API calls to improve performance while respecting rate limits.
    """
    session = freshservice_session()
    safe_limit = MAX_SIMILAR_TICKETS if limit is None else max(0, limit)
    if safe_limit > MAX_SIMILAR_TICKETS:
        logger.warning(
            "Requested similar ticket limit %s exceeds MAX_SIMILAR_TICKETS=%s; capping to %s.",
            safe_limit,
            MAX_SIMILAR_TICKETS,
            MAX_SIMILAR_TICKETS,
        )
        safe_limit = MAX_SIMILAR_TICKETS

    # Collect ticket IDs with their metadata for parallel processing
    tickets_to_fetch: List[tuple[int, str, dict, float]] = []
    for doc, meta, dist in results:
        if len(tickets_to_fetch) >= safe_limit:
            break
        ticket_id = meta.get("ticket_id")
        if ticket_id:
            try:
                tickets_to_fetch.append((int(ticket_id), doc, meta, dist))
            except (ValueError, TypeError):
                continue
    
    if not tickets_to_fetch:
        return []
    
    # Use parallel execution with limited concurrency to respect rate limits
    # Limit to 5 concurrent requests to avoid overwhelming the API
    max_workers = min(5, len(tickets_to_fetch))
    contexts: List[TicketContext] = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_ticket = {
            executor.submit(_fetch_ticket_context, session, ticket_id, dist): (doc, meta, dist)
            for ticket_id, doc, meta, dist in tickets_to_fetch
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_ticket):
            doc, meta, dist = future_to_ticket[future]
            try:
                ticket_ctx = future.result()
                contexts.append(ticket_ctx)
            except Exception as exc:
                logger.debug(f"Failed to fetch ticket context: {exc}")
                # Fallback to metadata-based context
                ticket_ctx = _fallback_ticket_context(doc, meta, dist)
                contexts.append(ticket_ctx)
    
    # Sort by distance to maintain order (parallel execution may complete out of order)
    contexts.sort(key=lambda ctx: ctx.distance)
    
    return contexts


def _fetch_ticket_context(session, ticket_id: int, distance: float) -> TicketContext:
    """Retrieve full ticket details + conversations with simple retry logic."""
    url = f"{FRESHSERVICE_BASE_URL}/tickets/{ticket_id}?include=conversations"
    attempts = 3
    for attempt in range(attempts):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code in (429, 503):
                # Respect Freshservice rate limiting/back-off guidance; the
                # staggered sleep keeps repeated guidance requests from hammering
                # the API during busy hours.
                if attempt < attempts - 1:
                    time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))
                    continue
            resp.raise_for_status()
            payload = resp.json() or {}
            ticket = payload.get("ticket", {}) or {}
            conversations = payload.get("conversations", []) or []
            return _build_context_from_api(session, ticket, conversations, distance)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))

    raise RuntimeError("Failed to fetch ticket context")


def _build_context_from_api(session, ticket: dict, conversations: list, distance: float) -> TicketContext:
    subject = (ticket.get("subject") or "").strip()
    description = _clean_text(ticket.get("description_text") or ticket.get("description") or "")
    notes = []
    for conv in conversations:
        body = conv.get("body_text") or conv.get("body") or ""
        if not body:
            continue
        # Private notes typically contain the remediation steps the agent took,
        # so we prioritise them over customer-facing replies when building the
        # evidence bundle for the guidance model.
        notes.append(
            ConversationNote(
                body=_truncate(_clean_text(body), 600),
                is_private=str(conv.get("private")) == "True" or conv.get("private") is True,
                author=_safe_trim(conv.get("user_name") or conv.get("to_emails")),
                created_at=conv.get("created_at"),
            )
        )

    group_id_val = ticket.get("group_id")
    group_name = _safe_trim(ticket.get("group_name"))
    if group_id_val is not None:
        try:
            group_id_int = int(group_id_val)
        except Exception:
            group_id_int = None
        else:
            if not group_name:
                group_name = get_group_name(group_id_int)
    else:
        group_id_int = None

    return TicketContext(
        ticket_id=int(ticket.get("id", 0) or 0),
        subject=subject,
        description=description,
        category=_safe_trim(ticket.get("category")),
        subcategory=_safe_trim(ticket.get("subcategory") or ticket.get("sub_category")),
        item=_safe_trim(ticket.get("item") or ticket.get("item_category")),
        group_id=group_id_int,
        group_name=group_name,
        responder_name=_safe_trim(ticket.get("responder_name") or ticket.get("responder_id")),
        distance=distance,
        notes=notes,
        notes_incomplete=False,
    )


def _fallback_ticket_context(doc: str, meta: dict, distance: float) -> TicketContext:
    """Build a minimal context object when the API lookup fails.

    Guidance still benefits from having a subject/description and at least one
    snippet of conversation, so we reuse whatever was present in the search
    metadata rather than aborting the entire guidance flow.
    """
    notes_raw = meta.get("conversations") or ""
    notes = []
    if notes_raw:
        if isinstance(notes_raw, list):
            for entry in notes_raw:
                body = ""
                if isinstance(entry, dict):
                    body = entry.get("body_text") or entry.get("body") or ""
                else:
                    body = str(entry)
                body = _truncate(_clean_text(body), 600)
                if not body:
                    continue
                notes.append(
                    ConversationNote(
                        body=body,
                        is_private=False,
                        author=None,
                        created_at=None,
                    )
                )
        else:
            notes.append(
                ConversationNote(
                    body=_truncate(_clean_text(str(notes_raw)), 600),
                    is_private=False,
                    author=None,
                    created_at=None,
                )
            )

    return TicketContext(
        ticket_id=int(meta.get("ticket_id") or 0),
        subject=_safe_trim(meta.get("subject")) or "",
        description=doc,
        category=_safe_trim(meta.get("category")),
        subcategory=_safe_trim(meta.get("subcategory") or meta.get("sub_category")),
        item=_safe_trim(meta.get("item") or meta.get("item_category")),
        group_id=_safe_int(meta.get("group_id")),
        group_name=_safe_trim(meta.get("group_name")),
        responder_name=_safe_trim(meta.get("responder_name")),
        distance=distance,
        notes=notes,
        notes_incomplete=True,
    )


def _clean_text(raw: str) -> str:
    """Clean HTML text to plain text."""
    if not raw:
        return ""
    from text_cleaning import html_to_text
    text = html_to_text(raw)
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _safe_trim(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _safe_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


