# =========================
# File: search_tickets.py
# =========================
from __future__ import annotations

import logging
import time
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from config import (
    chroma_collection,
    freshservice_session,
    FRESHSERVICE_BASE_URL,
    REQUEST_TIMEOUT,
    SEARCH_MAX_DISTANCE,
    RATE_LIMIT_SLEEP,
)
from text_cleaning import clean_description
from search_intent import (
    QueryIntent,
    ResultSignals,
    annotate_result_with_tokens,
    extract_query_intent,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

# --------------------------------
# WHERE filters (keep simple; mirrors a stable older version)
# --------------------------------
INCIDENT_WHERE: Dict[str, Any] = {"type": "incident"}
INCIDENT_CAP_WHERE: Dict[str, Any] = {"type": "Incident"}


# --------------------------------
# HTML → text (for seeding fallback)
# --------------------------------
def _html_to_text(html: Optional[str]) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


# --------------------------------
# Seed from a Freshservice ticket
# --------------------------------
def _fetch_ticket_subject_desc(ticket_id: int) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Return (subject, description_text_raw, description_html_raw, ticket_payload).
    Prefers server-side plain text; falls back to HTML→text if needed.
    """
    s = freshservice_session()
    r = s.get(f"{FRESHSERVICE_BASE_URL}/tickets/{int(ticket_id)}", timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    t = (r.json() or {}).get("ticket", {}) or {}
    subject = (t.get("subject") or "").strip()
    desc_text = (t.get("description_text") or "").strip()
    desc_html = (t.get("description") or "").strip()
    if not desc_text and desc_html:
        desc_text = _html_to_text(desc_html)
    return subject, desc_text, desc_html, t


def build_seed_text_from_ticket(ticket_id: int, *, clean: bool = True, use_ai_summary: bool = True) -> Tuple[str, Dict[str, str]]:
    """
    Compose query text from subject + description (optionally cleaned to match embedding).
    Uses AI summarization for better semantic matching with closed tickets.
    Returns (seed_text, meta_for_sidebar_display).
    """
    subject, desc_text_raw, desc_html_raw, ticket_payload = _fetch_ticket_subject_desc(ticket_id)
    desc_text_clean = clean_description(desc_text_raw) if clean else desc_text_raw
    
    # Create AI-enhanced search text for better semantic matching
    if use_ai_summary:
        try:
            from ai_summarizer import create_comprehensive_ticket_embedding_text
            seed_text = create_comprehensive_ticket_embedding_text(
                subject, desc_text_clean, ticket_id
            )
            ai_enhanced = True
        except Exception as e:
            logging.warning(f"AI summarization failed for ticket {ticket_id}: {e}")
            # Fallback to original method
            seed_text = f"{subject}\n\n{desc_text_clean}".strip() if (subject or desc_text_clean) else subject.strip()
            ai_enhanced = False
    else:
        seed_text = f"{subject}\n\n{desc_text_clean}".strip() if (subject or desc_text_clean) else subject.strip()
        ai_enhanced = False
    
    meta = {
        "subject": subject,
        "description_raw": desc_text_raw,
        "description_clean": desc_text_clean,
        "html_present": "yes" if bool(desc_html_raw) else "no",
        "ai_enhanced": "yes" if ai_enhanced else "no",
        "seed_text_preview": seed_text[:200] + "..." if len(seed_text) > 200 else seed_text,
        "description_html": desc_html_raw,
        "search_text": seed_text,
        "group_id": ticket_payload.get("group_id"),
        "group_name": ticket_payload.get("group_name"),
        "status": ticket_payload.get("status"),
        "ticket_id": ticket_payload.get("id"),
    }
    return seed_text, meta


# --------------------------------
# Chroma query helpers (stability-focused)
# --------------------------------
QUERY_TOP_N_DEFAULT = 1000       # mirror old script behavior
QUERY_TOP_N_CAP = 2000           # hard safety cap
QUERY_TOP_N_MIN = 50             # small but positive lower bound

# Relevance tuning weights (distance adjustments)
TOKEN_BONUS = 0.05
TOKEN_PENALTY = 0.04
CATEGORY_BONUS = 0.08
CATEGORY_PENALTY = 0.05
KEYWORD_BONUS = 0.015
KEYWORD_CAP = 3


def _compute_n_results(coll, top_n: Optional[int]) -> int:
    """
    Ensure we never pass None or 0 into coll.query(... n_results=...).
    Clamp to a safe, bounded positive integer.
    """
    if top_n is not None and top_n > 0:
        return max(QUERY_TOP_N_MIN, min(int(top_n), QUERY_TOP_N_CAP))
    # No explicit top_n: use collection size if available, else default
    try:
        count = int(coll.count())
        if count > 0:
            return max(QUERY_TOP_N_MIN, min(count, QUERY_TOP_N_DEFAULT))
    except Exception:
        pass
    return QUERY_TOP_N_DEFAULT


def _query(coll, query_text: str, n: Optional[int], where: Optional[dict]):
    n_results = _compute_n_results(coll, n)
    return coll.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def _triples(res) -> List[Tuple[str, dict, float]]:
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    out: List[Tuple[str, dict, float]] = []
    for d, m, dist in zip(docs, metas, dists):
        if dist is None:
            continue
        try:
            out.append((d or "", m or {}, float(dist)))
        except Exception:
            continue
    return out


# --------------------------------
# Assigned agent resolution (responder_id → name), with rate limit resilience
# --------------------------------
def _name_from_agent_payload(payload: dict) -> str:
    """
    Prefer agent-level first/last (old working behavior), then agent.name,
    then contact.name, then contact.first/last.
    """
    agent = (payload.get("agent") or {}) if isinstance(payload, dict) else {}
    # 1) agent.first_name + agent.last_name
    first = str(agent.get("first_name") or "").strip()
    last = str(agent.get("last_name") or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    # 2) agent.name
    name = str(agent.get("name") or "").strip()
    if name:
        return name
    # 3) agent.contact.name
    contact = agent.get("contact") or {}
    cname = str(contact.get("name") or "").strip()
    if cname:
        return cname
    # 4) contact.first_name + contact.last_name
    cfirst = str(contact.get("first_name") or "").strip()
    clast = str(contact.get("last_name") or "").strip()
    if cfirst or clast:
        return f"{cfirst} {clast}".strip()
    return "Unknown"


@lru_cache(maxsize=4096)
def _fetch_agent_name(agent_id: int) -> str:
    """
    Resolve agent name for responder_id with small retries on 429/503.
    """
    if not isinstance(agent_id, int):
        return "Unassigned"
    sess = freshservice_session()
    url = f"{FRESHSERVICE_BASE_URL}/agents/{agent_id}"
    attempts = 3
    for i in range(attempts):
        try:
            r = sess.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 503):
                if i < attempts - 1:
                    time.sleep(RATE_LIMIT_SLEEP)
                    continue
            r.raise_for_status()
            return _name_from_agent_payload(r.json() or {})
        except Exception:
            if i < attempts - 1:
                time.sleep(1)
                continue
            return "Unknown"


@lru_cache(maxsize=8192)
def _fetch_ticket_responder_id(ticket_id: int) -> Optional[int]:
    sess = freshservice_session()
    try:
        r = sess.get(f"{FRESHSERVICE_BASE_URL}/tickets/{ticket_id}", timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        t = (r.json() or {}).get("ticket", {}) or {}
        rid = t.get("responder_id")
        try:
            return int(rid) if rid is not None else None
        except Exception:
            return None
    except Exception:
        return None


def _resolve_assigned_agent(meta: dict) -> dict:
    """
    Ensure meta['responder_name'] reflects the assigned agent (responder_id).
    If missing/Unknown, look up responder_id (from meta or fresh /tickets/{id})
    and then fetch /agents/{id} to resolve a name.
    """
    out = dict(meta)
    name = (out.get("responder_name") or "").strip()
    if name and name.lower() not in {"unknown", "unassigned"}:
        return out

    rid = out.get("responder_id")
    rid_int: Optional[int] = None
    try:
        rid_int = int(rid) if rid is not None else None
    except Exception:
        rid_int = None

    if rid_int is None:
        tid = out.get("ticket_id")
        try:
            tid_int = int(tid)
        except Exception:
            tid_int = None
        if tid_int is not None:
            rid_int = _fetch_ticket_responder_id(tid_int)

    if rid_int is not None:
        resolved = _fetch_agent_name(rid_int).strip()
        if resolved and resolved.lower() not in {"unknown", "unassigned"}:
            out["responder_name"] = resolved
    return out


def _resolve_agents_for_results(results: List[Tuple[str, dict, float]]) -> List[Tuple[str, dict, float]]:
    return [(doc, _resolve_assigned_agent(meta), dist) for doc, meta, dist in results]


def _rerank_results(results: List[Tuple[str, dict, float]], intent: QueryIntent) -> List[Tuple[str, dict, float]]:
    reranked: List[Tuple[str, dict, float, float]] = []

    for doc, meta, dist in results:
        signals = annotate_result_with_tokens(doc, meta, intent)
        adjusted = _adjust_distance(dist, intent, signals)

        meta = dict(meta or {})
        relevance = dict(meta.get("relevance") or {})
        relevance.update(
            {
                "token_match": signals.token_match,
                "category_match": signals.category_match,
                "keyword_hits": signals.keyword_hits,
                "adjusted_distance": adjusted,
            }
        )
        if intent.tokens:
            relevance.setdefault("query_tokens", sorted(intent.tokens))
        if intent.has_category_path:
            relevance.setdefault(
                "query_category",
                {
                    "category": intent.category,
                    "subcategory": intent.subcategory,
                    "item": intent.item,
                },
            )
        meta["relevance"] = relevance
        reranked.append((doc, meta, dist, adjusted))

    reranked.sort(key=lambda entry: (entry[3], entry[2]))
    return [(doc, meta, dist) for doc, meta, dist, _ in reranked]


def _adjust_distance(dist: float, intent: QueryIntent, signals: ResultSignals) -> float:
    bonus = 0.0
    penalty = 0.0

    if intent.tokens:
        if signals.token_match:
            bonus += TOKEN_BONUS
        else:
            penalty += TOKEN_PENALTY

    if intent.has_category_path:
        if signals.category_match:
            bonus += CATEGORY_BONUS
        else:
            penalty += CATEGORY_PENALTY

    if signals.keyword_hits:
        bonus += min(signals.keyword_hits, KEYWORD_CAP) * KEYWORD_BONUS

    adjusted = dist + penalty - bonus
    return adjusted if adjusted > 0.0 else 0.0


def _apply_strict_filters(
    results: List[Tuple[str, dict, float]],
    *,
    intent: QueryIntent,
    require_token: bool,
    require_category: bool,
) -> List[Tuple[str, dict, float]]:
    filtered = results

    if require_token and intent.tokens:
        filtered = [r for r in filtered if r[1].get("relevance", {}).get("token_match")]

    if require_category and intent.has_category_path:
        filtered = [r for r in filtered if r[1].get("relevance", {}).get("category_match")]

    return filtered


# --------------------------------
# Retrieval pipeline (stable; simple WHERE chain)
# --------------------------------
def retrieve_similar_tickets(
    query_text: str,
    top_n: Optional[int] = None,
    max_distance: Optional[float] = None,
    intent: Optional[QueryIntent] = None,
    require_token_match: bool = False,
    require_category_match: bool = False,
) -> List[Tuple[str, dict, float]]:
    """
    Strategy:
      1) where={"type":"incident"}
      2) where={"type":"Incident"}
      3) where=None
    Then distance-filter and sort ascending.
    """
    coll = chroma_collection()
    threshold = float(max_distance) if max_distance is not None else float(SEARCH_MAX_DISTANCE)
    intent = intent or QueryIntent(raw_query=query_text, tokens=set(), keywords=set())

    attempts: List[Tuple[Optional[dict], str]] = [
        (INCIDENT_WHERE, "incident"),
        (INCIDENT_CAP_WHERE, "Incident"),
        (None, "no-where"),
    ]

    for where, note in attempts:
        try:
            res = _query(coll, query_text, top_n, where)
        except Exception as e:
            logging.warning(f"[warn] query attempt '{note}' failed: {e}")
            # tiny fallback
            try:
                res = coll.query(
                    query_texts=[query_text],
                    n_results=QUERY_TOP_N_MIN,
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as e2:
                logging.warning(f"[warn] tiny-fallback '{note}' also failed: {e2}")
                continue

        triples = _triples(res)
        kept = [(d, m, dist) for (d, m, dist) in triples if dist <= threshold]
        if kept:
            kept.sort(key=lambda x: x[2])
            resolved = _resolve_agents_for_results(kept)
            reranked = _rerank_results(resolved, intent)
            return _apply_strict_filters(
                reranked,
                intent=intent,
                require_token=require_token_match,
                require_category=require_category_match,
            )

    return []


# --------------------------------
# Summary helpers (used by UI)
# --------------------------------
def summarize(results: List[Tuple[str, dict, float]]) -> dict:
    total = len(results)

    def _pct(n: int) -> float:
        return round((n / total * 100.0), 1) if total else 0.0

    agents = Counter(m.get("responder_name", "Unknown") for _d, m, _ in results)
    groups = Counter(m.get("group_name", "Unknown") for _d, m, _ in results)
    paths = Counter((m.get("category"), m.get("subcategory"), m.get("item")) for _d, m, _ in results)

    top_agents = [{"name": k or "Unknown", "pct": _pct(v)} for k, v in agents.most_common(2)]
    top_groups = [{"name": k or "Unknown", "pct": _pct(v)} for k, v in groups.most_common(2)]

    top_paths: List[Dict[str, Any]] = []
    for (cat, sub, item), v in paths.most_common(2):
        path_str = " → ".join(p for p in (cat, sub, item) if p) if (cat or sub or item) else "—"
        top_paths.append({"path": path_str, "pct": _pct(v)})

    return {"total": total, "top_agents": top_agents, "top_groups": top_groups, "top_paths": top_paths}


# --------------------------------
# (Optional) CLI for quick checks
# --------------------------------
if __name__ == "__main__":
    import argparse, webbrowser, os as _os

    parser = argparse.ArgumentParser(description="Semantic search over Freshservice tickets.")
    parser.add_argument("query", nargs="*", help="Free text query. Omit if using --seed-ticket.")
    parser.add_argument("--seed-ticket", type=int, help="Use this ticket's subject+cleaned description as the query.")
    parser.add_argument("--no-clean-seed", action="store_true", help="If set with --seed-ticket, do not clean the description.")
    parser.add_argument("--no-ai-summary", action="store_true", help="Disable AI summarization for ticket seeding (use raw text).")
    parser.add_argument("--max-distance", type=float, default=SEARCH_MAX_DISTANCE, help="Similarity cutoff.")
    parser.add_argument("--open", nargs="?", const="1", help="Open the top or Nth displayed result in the browser.")
    parser.add_argument(
        "--require-token",
        action="store_true",
        help="Only include results that match high-signal tokens detected in the query.",
    )
    parser.add_argument(
        "--same-category-only",
        action="store_true",
        help="Only include results that share the seed ticket's category path (requires --seed-ticket).",
    )
    args = parser.parse_args()

    if args.seed_ticket:
        seed_text, seed_meta = build_seed_text_from_ticket(
            args.seed_ticket, 
            clean=(not args.no_clean_seed),
            use_ai_summary=(not args.no_ai_summary)
        )
        query_text = seed_text
        ai_status = "AI-enhanced" if not args.no_ai_summary else "raw text"
        logging.info(f"[seed] ticket {args.seed_ticket} (cleaned={not args.no_clean_seed}, {ai_status})")
    else:
        if not args.query:
            parser.error("Provide a free-text query or use --seed-ticket.")
        query_text = " ".join(args.query).strip()
        seed_meta = None

    intent = extract_query_intent(query_text, seed_metadata=seed_meta)
    if intent.tokens:
        logging.info(f"[info] detected tokens: {', '.join(sorted(intent.tokens))}")
    if args.same_category_only and not intent.has_category_path:
        logging.warning("[warn] --same-category-only set but no category metadata available.")

    results = retrieve_similar_tickets(
        query_text,
        top_n=None,
        max_distance=args.max_distance,
        intent=intent,
        require_token_match=args.require_token,
        require_category_match=args.same_category_only,
    )

    if not results and (args.require_token or args.same_category_only):
        logging.info("[info] No results after strict filtering; consider relaxing strict options.")

    logging.info(f"[info] results={len(results)} (≤ {args.max_distance})")
    for idx, (_doc, m, dist) in enumerate(results[:30], 1):
        tid = m.get("ticket_id")
        subject = (m.get("subject") or "")[:90]
        agent = m.get("responder_name", "Unknown")
        group = m.get("group_name", "Unknown")
        path = " → ".join(p for p in (m.get("category"), m.get("subcategory"), m.get("item")) if p)
        logging.info(f"{idx:>2}. tid={tid} dist={dist:.4f} | {subject} | {agent} / {group} | {path}")

    if args.open and results:
        try:
            n = max(1, int(args.open))
        except Exception:
            n = 1
        idx = min(n, len(results)) - 1
        tid = results[idx][1].get("ticket_id")
        dom = _os.getenv("FRESHSERVICE_DOMAIN", "").strip()
        if tid and dom:
            webbrowser.open_new_tab(f"https://{dom}/helpdesk/tickets/{tid}")
