# File: freshservice.py
from __future__ import annotations

import logging
import math
import os
import time
from typing import Dict, List, Optional, Any

from bs4 import BeautifulSoup

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
from text_cleaning import clean_description

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Toggles (can be overridden in api.env)
INCLUDE_CONV_IN_EMBED = os.getenv("INCLUDE_CONVERSATIONS_IN_EMBED", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_DESCRIPTION_CLEANING = os.getenv("ENABLE_DESCRIPTION_CLEANING", "1").strip().lower() in {"1", "true", "yes", "on"}

# ---------------------------
# Utilities
# ---------------------------
def _html_to_text(html: Optional[str]) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def trim_to_token_limit(text: str, max_words: int) -> str:
    words = (text or "").split()
    return " ".join(words[:max_words]) if len(words) > max_words else (text or "")


_AGENT_NAME_CACHE: Dict[int, str] = {}
_GROUP_NAME_CACHE: Dict[int, str] = {}


def _get_agent_name(session, agent_id) -> str:
    if agent_id is None:
        return "Unassigned"
    try:
        agent_id = int(agent_id)
    except Exception:
        return "Unassigned"

    if agent_id in _AGENT_NAME_CACHE:
        return _AGENT_NAME_CACHE[agent_id]

    url = f"{FRESHSERVICE_BASE_URL}/agents/{agent_id}"
    attempts = 3
    for attempt in range(attempts):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 503):
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logging.info(
                    f"[rate] agent lookup {agent_id} -> {r.status_code}; sleeping {wait:.2f}s"
                )
                time.sleep(wait)
                continue
            r.raise_for_status()
            agent = (r.json() or {}).get("agent", {}) or {}
            contact = (agent.get("contact") or {}) if isinstance(agent, dict) else {}
            name = (contact.get("name") or "").strip()
            if not name:
                first = (contact.get("first_name") or "").strip()
                last = (contact.get("last_name") or "").strip()
                name = f"{first} {last}".strip()
            name = name or "Unknown"
            _AGENT_NAME_CACHE[agent_id] = name
            return name
        except Exception as exc:
            if attempt < attempts - 1:
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logging.info(
                    f"[warn] agent lookup {agent_id} failed ({exc}); retrying in {wait:.2f}s"
                )
                time.sleep(wait)
            else:
                logging.warning(f"[warn] agent lookup {agent_id} failed; using 'Unknown'")
    _AGENT_NAME_CACHE[agent_id] = "Unknown"
    return "Unknown"


def _get_group_name(session, group_id) -> str:
    if group_id is None:
        return "Unknown"
    try:
        group_id = int(group_id)
    except Exception:
        return "Unknown"

    if group_id in _GROUP_NAME_CACHE:
        return _GROUP_NAME_CACHE[group_id]

    url = f"{FRESHSERVICE_BASE_URL}/groups/{group_id}"
    attempts = 3
    for attempt in range(attempts):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 503):
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logging.info(
                    f"[rate] group lookup {group_id} -> {r.status_code}; sleeping {wait:.2f}s"
                )
                time.sleep(wait)
                continue
            r.raise_for_status()
            name = ((r.json() or {}).get("group", {}) or {}).get("name", "") or "Unknown"
            _GROUP_NAME_CACHE[group_id] = name
            return name
        except Exception as exc:
            if attempt < attempts - 1:
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logging.info(
                    f"[warn] group lookup {group_id} failed ({exc}); retrying in {wait:.2f}s"
                )
                time.sleep(wait)
            else:
                logging.warning(f"[warn] group lookup {group_id} failed; using 'Unknown'")
    _GROUP_NAME_CACHE[group_id] = "Unknown"
    return "Unknown"


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
            txt = c.get("body_text") or _html_to_text(c.get("body"))
            if txt:
                texts.append(txt)
        return texts


def _fetch_all_tickets(session) -> List[dict]:
    page = 1
    tickets: List[dict] = []
    while True:
        url = f"{FRESHSERVICE_BASE_URL}/tickets?per_page=100&page={page}"
        r = session.get(url, timeout=REQUEST_TIMEOUT)
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
def main() -> None:
    session = freshservice_session()
    coll = chroma_collection()

    total = added = duplicates = 0
    filtered_status = filtered_type = 0

    tickets = _fetch_all_tickets(session)
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
            description = _html_to_text(t.get("description") or "")
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
        agent_name = _get_agent_name(session, responder_id)
        group_name = _get_group_name(session, group_id)

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
    main()
