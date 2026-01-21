# File: freshservice.py
from __future__ import annotations

import argparse
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from config import (
    chroma_collection,
    freshservice_session,
    FRESHSERVICE_BASE_URL,
    INGEST_MAX_TOKENS,
    INGEST_STATUS_CODE,
    REQUEST_TIMEOUT,
    RATE_LIMIT_SLEEP,
)

# Use the shared, single-source cleaner
from text_cleaning import clean_description, html_to_text
from agent_resolver import get_agent_name, get_group_name

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Toggles (can be overridden in api.env)
INCLUDE_CONV_IN_EMBED = os.getenv("INCLUDE_CONVERSATIONS_IN_EMBED", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_DESCRIPTION_CLEANING = os.getenv("ENABLE_DESCRIPTION_CLEANING", "1").strip().lower() in {"1", "true", "yes", "on"}

# ---------------------------
# Utilities
# ---------------------------
def trim_to_token_limit(text: str, max_words: int) -> str:
    words = (text or "").split()
    return " ".join(words[:max_words]) if len(words) > max_words else (text or "")




def _fetch_conversations(session, ticket_id: int) -> List[str]:
    url = f"{FRESHSERVICE_BASE_URL}/tickets/{ticket_id}/conversations"
    while True:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            logging.info(f"[rate] 429 on conversations ticket={ticket_id}; sleeping {RATE_LIMIT_SLEEP}s")
            time.sleep(RATE_LIMIT_SLEEP)
            continue
        if not r.ok:
            return []
        convs = (r.json() or {}).get("conversations", []) or []
        texts: List[str] = []
        for c in convs:
            txt = c.get("body_text") or html_to_text(c.get("body"))
            if txt:
                texts.append(txt)
        return texts


def _fetch_all_tickets(session, *, updated_since: Optional[str] = None) -> List[dict]:
    page = 1
    tickets: List[dict] = []
    while True:
        url = f"{FRESHSERVICE_BASE_URL}/tickets"
        params = {"per_page": 100, "page": page}
        if updated_since:
            params["updated_since"] = updated_since
        r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            logging.info(f"[rate] 429 on tickets page={page}; sleeping {RATE_LIMIT_SLEEP}s")
            time.sleep(RATE_LIMIT_SLEEP)
            continue
        if not r.ok:
            break
        batch = (r.json() or {}).get("tickets", []) or []
        if not batch:
            break
        tickets.extend(batch)
        page += 1
    return tickets


def _exists(coll, ticket_id: int) -> bool:
    try:
        res = coll.get(ids=[str(ticket_id)])
        return bool(res.get("ids"))
    except Exception:
        return False


# ---------------------------
# Metadata sanitation (Chroma demands primitives; no None)
# ---------------------------
_ALLOWED = (bool, int, float, str)


def _coerce_value(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return v
    if isinstance(v, str):
        return v
    try:
        return str(v)
    except Exception:
        return ""


def sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for k, v in meta.items():
        cv = _coerce_value(v)
        if not isinstance(cv, _ALLOWED):
            cv = str(cv) if cv is not None else ""
        clean[k] = cv
    return clean


# ---------------------------
# Main ingest
# ---------------------------
def _parse_since_days(value: str) -> Optional[str]:
    if value is None:
        return None
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None
    if days <= 0:
        return None
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return since.isoformat()


def main(*, updated_since: Optional[str] = None) -> None:
    session = freshservice_session()
    coll = chroma_collection()

    total = added = duplicates = 0
    filtered_status = filtered_type = 0

    tickets = _fetch_all_tickets(session, updated_since=updated_since)
    for t in tickets:
        total += 1

        # Status & Type filters
        try:
            status = int(t.get("status", 0))
        except Exception:
            status = 0
        if status != INGEST_STATUS_CODE:
            filtered_status += 1
            continue

        ttype = (t.get("type") or "").strip().lower()
        if ttype != "incident":
            filtered_type += 1
            continue

        tid = int(t["id"])
        if _exists(coll, tid):
            duplicates += 1
            logging.info(f"[skip] ticket={tid} already embedded")
            continue

        subject = (t.get("subject") or "").strip()

        # Prefer plain text; fallback to HTML→text; then clean if enabled
        description = (t.get("description_text") or "").strip()
        if not description:
            description = html_to_text(t.get("description") or "")
        if ENABLE_DESCRIPTION_CLEANING:
            description = clean_description(description)

        # Conversations in metadata only (unless toggled)
        conv_text = "\n\n".join(_fetch_conversations(session, tid))

        # Build embedding text
        parts = [subject, "", description]
        if INCLUDE_CONV_IN_EMBED and conv_text:
            parts.extend(["", conv_text])
        emb_text = trim_to_token_limit("\n".join(parts), INGEST_MAX_TOKENS)

        # Best-effort agent/group names
        responder_id = t.get("responder_id")
        group_id = t.get("group_id")
        agent_name = get_agent_name(responder_id)
        group_name = get_group_name(group_id)

        raw_meta: Dict[str, Any] = {
            "doc_type": "core",  # searchable doc marker
            "ticket_id": tid,
            "subject": subject,
            "requester_id": t.get("requester_id"),
            "responder_id": responder_id,
            "responder_name": agent_name,
            "group_id": group_id,
            "group_name": group_name,
            "status": status,
            "type": t.get("type"),
            "category": t.get("category"),
            "subcategory": t.get("subcategory") or t.get("sub_category"),
            "item": t.get("item") or t.get("item_category"),
            "priority": t.get("priority"),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "conversations": conv_text,  # viewable, not embedded (by default)
        }

        metadata = sanitize_metadata(raw_meta)

        try:
            coll.add(documents=[emb_text], metadatas=[metadata], ids=[str(tid)])
            added += 1
            logging.info(f"[ok]   embedded ticket={tid} chars={len(emb_text)}")
        except Exception as e:
            bad_keys = [k for k, v in metadata.items() if not isinstance(v, _ALLOWED)]
            logging.error(f"[error] add failed for ticket={tid}: {e}")
            if bad_keys:
                logging.error(f"[debug] metadata non-primitive keys: {bad_keys}")
            continue

    logging.info(
        f"[done] total={total} added={added} duplicates={duplicates} "
        f"filtered_status={filtered_status} (status=={INGEST_STATUS_CODE}) "
        f"filtered_type={filtered_type} (type!=incident)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Freshservice tickets into ChromaDB.")
    parser.add_argument(
        "--since-days",
        type=str,
        default=os.getenv("INGEST_SINCE_DAYS"),
        help="Only ingest tickets updated in the last N days (env: INGEST_SINCE_DAYS).",
    )
    args = parser.parse_args()
    updated_since = _parse_since_days(args.since_days)
    main(updated_since=updated_since)
