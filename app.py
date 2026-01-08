# =========================
# File: app.py
# =========================
from __future__ import annotations

import json
import logging
import os
import re
import time
import traceback
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import with error handling
try:
    from config import (
        CHROMA_COLLECTION_NAME,
        SEARCH_MAX_DISPLAY,
        REQUEST_TIMEOUT,
        FRESHSERVICE_BASE_URL,
        RATE_LIMIT_SLEEP,
        freshservice_session,
        get_ticket_url,
    )
    from search_tickets import (
        retrieve_similar_tickets,
        summarize,
        build_seed_text_from_ticket,
    )
    from search_intent import extract_query_intent
    from search_context import gather_ticket_contexts, load_category_tree, TicketContext
    from ai_recommendations import AIGuidance, generate_guidance
    from debug_utils import (
        SystemDiagnostics,
        handle_streamlit_error,
        display_system_status,
        safe_import
    )
    IMPORTS_SUCCESSFUL = True
except Exception as e:
    logger.error(f"Import error: {e}")
    logger.error(traceback.format_exc())
    IMPORTS_SUCCESSFUL = False

# --------------------------------
# Page config & lightweight styles
# --------------------------------
st.set_page_config(page_title="Freshservice Semantic Search", layout="wide")
# Use generic selectors (avoid Streamlit's ephemeral emotion classnames)
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; }
      details { padding: 0.25rem 0.5rem; }
      .dist-chip {
        background: #F6A700; color: #111;
        padding: 2px 8px; border-radius: 12px; font-weight: 600;
        font-size: 12px;
      }
      .chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
      }
      .chip-small {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 8px;
        font-size: 10px;
        font-weight: 500;
        margin-right: 4px;
        margin-bottom: 2px;
      }
      .chip-good { background: #34d399; color: #0f172a; }
      .chip-warn { background: #f97316; color: #111; }
      .chip-muted { background: #334155; color: #e2e8f0; }
      .muted { color: #666; font-size: 0.9rem; }
      .compact-muted { color: #666; font-size: 0.8rem; line-height: 1.2; }
      .compact-ticket { color: #888; font-size: 0.85rem; font-weight: 600; }
      .compact-summary { color: #777; font-size: 0.8rem; line-height: 1.3; margin-top: 2px; }
      .compact-summary-no-margin { color: #777; font-size: 0.8rem; line-height: 1.3; margin-top: 0px; }
      .compact-summary-tight { color: #777; font-size: 0.8rem; line-height: 1.2; margin-top: -4px; margin-bottom: 0px; }
      .path  { color: #444; font-size: 0.9rem; }
      .kpi   { font-size: 28px; font-weight: 700; }
      .label { color: #666; font-size: 0.9rem; }
      section[data-testid="stSidebar"] .block-container {
        position: sticky;
        top: 0;
        height: 100vh;
        overflow-y: auto;
      }
      /* Make expand/collapse buttons cleaner */
      .stButton > button {
        width: 100%;
        height: 1.5rem;
        padding: 0;
        font-size: 0.8rem;
        border: none;
        background: transparent;
        color: #666;
      }
      .stButton > button:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #999;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔎 Nexus")

# Check if imports were successful
if not IMPORTS_SUCCESSFUL:
    st.error("❌ **Critical Error: Failed to import required modules**")
    st.error("Please check the system diagnostics below and resolve any dependency issues.")
    
    # Show system diagnostics
    try:
        from debug_utils import display_system_status
        display_system_status()
    except Exception as e:
        st.error(f"Failed to load diagnostics: {e}")
    
    st.stop()

# IMPORTANT: We always fetch a relaxed set, then bucket by rank for UX.
RELAXED_MAX_DISTANCE = 1.0
try:
    from config import SEARCH_MAX_DISTANCE
    st.caption(f"Collection: **{CHROMA_COLLECTION_NAME}** · Retrieval cutoff ≤ **{RELAXED_MAX_DISTANCE:.2f}** · Display cutoff ≤ **{SEARCH_MAX_DISTANCE:.2f}**")
except Exception as e:
    st.caption("Collection: **Unknown** · Retrieval cutoff ≤ **1.00** · Display cutoff ≤ **0.70**")
    logger.error(f"Failed to load collection name: {e}")

# Add debug mode toggle
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# ----------------------------
# Helpers
# ----------------------------
def _ticket_url(tid: Optional[int]) -> Optional[str]:
    if not tid:
        return None
    try:
        return get_ticket_url(tid)
    except Exception:
        return None


def _detect_ticket_id(raw: str) -> Optional[int]:
    """Recognize a Freshservice ticket id (4–6 digits), optionally prefixed by '#'."""
    m = re.match(r"^\s*#?(\d{4,6})\s*$", raw or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _bucket_by_percentile(results: List[Tuple[str, dict, float]]):
    """
    Partition results (sorted by distance asc) into UX buckets by rank:
      - Most Similar: top 20%
      - Similar:      next 30% (21–50%)
      - Related:      next 30% (51–80%)
      - Loose:        remaining (81–100%)
    Always ensures at least 1 item in the top bucket when results exist.
    """
    if not results:
        return {"most": [], "similar": [], "related": [], "loose": []}

    n = len(results)
    top_end = max(1, int(round(n * 0.20)))
    sim_end = max(top_end, int(round(n * 0.50)))
    rel_end = max(sim_end, int(round(n * 0.80)))

    most = results[:top_end]
    similar = results[top_end:sim_end]
    related = results[sim_end:rel_end]
    loose = results[rel_end:]
    return {"most": most, "similar": similar, "related": related, "loose": loose}


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            value = stripped
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


@lru_cache(maxsize=1)
def _status_choices() -> List[Tuple[int, str]]:
    fallback = [
        (2, "Open"),
        (6, "Work In Progress"),
        (3, "Pending"),
        (10, "Pending Approval"),
        (7, "On Hold"),
        (8, "Scheduled"),
        (9, "Shipped"),
        (4, "Resolved"),
        (5, "Closed"),
    ]
    path = os.path.join(os.path.dirname(__file__), "raw_ticket_fields.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for field in data:
            if field.get("name") == "status" and field.get("choices"):
                choices: List[Tuple[int, str]] = []
                for choice in field["choices"]:
                    cid = _safe_int(choice.get("id"))
                    label = (choice.get("value") or "").strip()
                    if cid is None or not label:
                        continue
                    choices.append((cid, label))
                if choices:
                    return choices
                break
    except Exception as exc:
        logger.debug("Falling back to default status choices: %s", exc)
    return fallback


def _status_label(status_id: Optional[int]) -> str:
    if status_id is None:
        return "Unknown"
    lookup = dict(_status_choices())
    return lookup.get(status_id, f"Status {status_id}")


@st.cache_data(show_spinner=False)
def _assignment_group_options() -> List[Tuple[int, str]]:
    session = freshservice_session()
    groups: Dict[int, str] = {}
    page = 1
    retries = 0

    while page <= 50:
        try:
            resp = session.get(
                f"{FRESHSERVICE_BASE_URL}/groups",
                params={"page": page, "per_page": 100},
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Failed to load assignment groups (page %s): %s", page, exc)
            break

        if resp.status_code == 429:
            retries += 1
            if retries >= 3:
                logger.warning("Aborting assignment group fetch after repeated rate limits.")
                break
            time.sleep(RATE_LIMIT_SLEEP)
            continue

        retries = 0
        if resp.status_code >= 400:
            logger.warning(
                "Failed to load assignment groups: %s %s",
                resp.status_code,
                resp.text[:120],
            )
            break

        payload = resp.json() or {}
        page_groups = payload.get("groups") or payload.get("data") or []
        if not page_groups:
            break

        for group in page_groups:
            gid = _safe_int(group.get("id"))
            if gid is None:
                continue
            name = (group.get("name") or "").strip() or f"Group {gid}"
            groups[gid] = name

        if len(page_groups) < 100:
            break
        page += 1

    return sorted(groups.items(), key=lambda item: item[1].lower())


def _render_card(doc: str, m: dict, dist: float, show_desc_default: bool = False):
    raw_tid = m.get("ticket_id")
    tid = _safe_int(raw_tid)
    url = _ticket_url(tid)
    subject = (m.get("subject") or "—").strip()
    agent = m.get("responder_name", "Unknown") or "Unknown"
    group_name = m.get("group_name", "Unknown") or "Unknown"
    group_id = _safe_int(m.get("group_id"))
    status_id = _safe_int(m.get("status"))
    status_text = _status_label(status_id)
    path = " → ".join(p for p in (m.get("category"), m.get("subcategory"), m.get("item")) if p)
    relevance = m.get("relevance", {})
    adjusted = relevance.get("adjusted_distance", dist)

    if adjusted <= 0.4:
        dist_class = "chip chip-good"
    elif adjusted <= 0.7:
        dist_class = "chip chip-warn"
    else:
        dist_class = "chip chip-muted"

    ticket_display = tid if tid is not None else raw_tid

    # Create a unique key for this card's expander state
    card_key = f"card_expand_{ticket_display}_{hash(subject)}"
    
    # Check if this card should be expanded
    is_expanded = st.session_state.get(card_key, show_desc_default)

    with st.container(border=True):
        if is_expanded:
            # Expanded view - show all details
            # Line 1: Ticket number, subject, closeness rating, collapse button
            line1_cols = st.columns([1, 7, 1, 0.5])
            
            with line1_cols[0]:
                st.markdown(f"<div class='compact-ticket'>#{ticket_display}</div>", unsafe_allow_html=True)
            
            with line1_cols[1]:
                if url:
                    st.markdown(f"**{subject}** &nbsp;[🔗]({url})")
                else:
                    st.markdown(f"**{subject}**")
            
            with line1_cols[2]:
                st.markdown(f"<div style='text-align:right;'><span class='{dist_class}'>{dist:.3f}</span></div>", unsafe_allow_html=True)
            
            with line1_cols[3]:
                if st.button("▲", key=f"collapse_{card_key}", help="Collapse"):
                    st.session_state[card_key] = False
                    st.rerun()
            
            # Full description
            st.markdown("**Description:**")
            st.write(doc or "—")
            
            # Metadata in organized format
            col1, col2 = st.columns(2)
            with col1:
                if path:
                    st.markdown(f"**Category:** {path}")
                st.markdown(f"**Agent:** {agent}")
            with col2:
                group_bits = group_name
                if group_id is not None and (group_bits is None or f"#{group_id}" not in group_bits):
                    group_bits = f"{group_name} (#{group_id})" if group_name else f"Group #{group_id}"
                st.markdown(f"**Group:** {group_bits or 'Unknown'}")
                st.markdown(f"**Status:** {status_text}")
            
            # Relevance badges
            badge_html = []
            if relevance.get("token_match"):
                badge_html.append("<span class='chip-small chip-good'>Token Match</span>")
            elif relevance.get("query_tokens"):
                badge_html.append("<span class='chip-small chip-muted'>Missing Tokens</span>")
            if relevance.get("category_match"):
                badge_html.append("<span class='chip-small chip-good'>Category Match</span>")
            elif relevance.get("query_category"):
                badge_html.append("<span class='chip-small chip-muted'>Different Category</span>")
            if badge_html:
                st.markdown("**Relevance:** " + "".join(badge_html), unsafe_allow_html=True)
        
        else:
            # Collapsed view - just the essential info
            # Line 1: Ticket number, subject, closeness rating, expand button
            line1_cols = st.columns([1, 7, 1, 0.5])
            
            with line1_cols[0]:
                st.markdown(f"<div class='compact-ticket'>#{ticket_display}</div>", unsafe_allow_html=True)
            
            with line1_cols[1]:
                if url:
                    st.markdown(f"**{subject}** &nbsp;[🔗]({url})")
                else:
                    st.markdown(f"**{subject}**")
            
            with line1_cols[2]:
                st.markdown(f"<div style='text-align:right;'><span class='{dist_class}'>{dist:.3f}</span></div>", unsafe_allow_html=True)
            
            with line1_cols[3]:
                if st.button("▼", key=f"expand_{card_key}", help="Expand"):
                    st.session_state[card_key] = True
                    st.rerun()
            
            # Line 2: AI summary (compact preview) - no space above
            preview = _extract_preview_text(doc, subject, limit=100)
            if preview:
                st.markdown(f"<div class='compact-summary-tight'>{preview}</div>", unsafe_allow_html=True)


def _extract_preview_text(doc: str, subject: str, limit: int = 100) -> str:
    """
    Extract preview text from the document. Currently shows raw description text.
    TODO: This should ideally show AI-generated summaries for better UX.
    """
    text = doc or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    # Avoid repeating the subject line in the preview if present
    normalized_subject = subject.strip().lower()
    if lines[0].lower() == normalized_subject and len(lines) > 1:
        candidate = lines[1]
    else:
        candidate = lines[0]

    if len(candidate) > limit:
        candidate = candidate[: limit - 1].rstrip() + "…"
    return candidate




def _render_guidance(
    guidance, 
    contexts, 
    ticket_id: Optional[int], 
    seed_meta: Optional[Dict[str, Any]],
    categories_tree: Optional[dict] = None
) -> None:
    logger.info('render guidance start', extra={'ticket_id': ticket_id, 'has_category': bool(guidance.recommended_category)})

    agent_text = (guidance.agent_markdown or '').strip()
    if agent_text:
        st.markdown(agent_text)
    else:
        st.info('AI guidance did not return narrative instructions.')

    recommended_category = guidance.recommended_category or []
    confidence = guidance.confidence or 'Unknown'
    if recommended_category:
        path = ' → '.join(recommended_category)
        st.markdown(f"**Suggested category:** {path} _(confidence: {confidence})_")
    else:
        st.markdown(f"**Confidence:** {confidence}")

    recommended_group_name = (guidance.recommended_group or '').strip()
    resolved_group_name = recommended_group_name or None
    recommended_group_id = None
    if recommended_group_name:
        for ctx in contexts:
            ctx_name = (ctx.group_name or '').strip()
            if ctx_name and ctx_name.lower() == recommended_group_name.lower():
                resolved_group_name = ctx_name
                if ctx.group_id is not None:
                    recommended_group_id = ctx.group_id
                break
        group_label = resolved_group_name or recommended_group_name
        if group_label:
            st.markdown(f"**Suggested assignment group:** {group_label}")

    if guidance.supporting_tickets:
        with st.expander('Supporting tickets'):
            for item in guidance.supporting_tickets:
                supporting_tid = item.get('ticket_id')
                rationale = item.get('rationale') or item.get('reason') or ''
                st.write(f"- Ticket {supporting_tid}: {rationale}")

    if not ticket_id:
        st.caption('Open a ticket to apply updates.')
        return

    current_group_id = _safe_int((seed_meta or {}).get('group_id'))
    current_group_name = (seed_meta or {}).get('group_name')

    meta_for_category = seed_meta or {}
    current_category_parts: List[str] = []
    category_root = meta_for_category.get('category') or meta_for_category.get('category_name')
    subcategory_val = meta_for_category.get('subcategory') or meta_for_category.get('sub_category')
    item_val = meta_for_category.get('item') or meta_for_category.get('item_category')

    for value in (category_root, subcategory_val, item_val):
        if value:
            current_category_parts.append(str(value))

    current_category_label = ' → '.join(current_category_parts) if current_category_parts else 'Not set'
    current_group_display = (
        current_group_name
        or (f"Group {current_group_id}" if current_group_id is not None else 'Unassigned')
    )

    group_options = _assignment_group_options()
    group_lookup = {gid: name for gid, name in group_options}
    group_option_values = [None] + [gid for gid, _ in group_options]

    if recommended_group_id is None and recommended_group_name:
        for gid, name in group_options:
            if name.lower() == recommended_group_name.lower():
                recommended_group_id = gid
                resolved_group_name = name
                break

    if recommended_group_id is not None and recommended_group_id not in group_option_values:
        group_option_values.append(recommended_group_id)
        group_lookup[recommended_group_id] = (
            resolved_group_name or recommended_group_name or f"Group {recommended_group_id}"
        )

    if current_group_id is not None and current_group_id not in group_option_values:
        group_option_values.append(current_group_id)
        group_lookup[current_group_id] = current_group_name or f"Group {current_group_id}"

    group_option_values = list(dict.fromkeys(group_option_values))

    if recommended_group_id in group_option_values:
        default_group_value = recommended_group_id
    elif current_group_id in group_option_values:
        default_group_value = current_group_id
    else:
        default_group_value = None

    if default_group_value in group_option_values:
        default_group_index = group_option_values.index(default_group_value)
    else:
        default_group_index = 0

    def _format_group_option(gid: Optional[int]) -> str:
        if gid is None:
            if current_group_id is None:
                return 'Keep current'
            current_label = group_lookup.get(current_group_id) or current_group_name or f"Group {current_group_id}"
            return f"Keep current ({current_label})"
        return group_lookup.get(gid, f"Group {gid}")

    st.markdown(f"**Apply to ticket #{ticket_id}**")
    cat_col, group_col = st.columns([1.2, 1.4])

    with cat_col:
        st.caption('Category')
        if recommended_category:
            st.write(' → '.join(recommended_category))
        else:
            st.caption('No category suggestion provided.')
        st.caption(f"Current: {current_category_label}")

    with group_col:
        st.caption('Assignment group')
        st.caption(f"Current: {current_group_display}")
        if len(group_option_values) > 1:
            selected_group_id = st.selectbox(
                'Assignment group',
                options=group_option_values,
                index=default_group_index,
                format_func=_format_group_option,
                key=f"group_select_seed_{ticket_id}",
                label_visibility='collapsed',
            )
        else:
            st.info('Group list unavailable; enter an id manually.')
            placeholder = f"{current_group_id}" if current_group_id is not None else ''
            raw_group = st.text_input(
                'Assignment group id',
                value=placeholder,
                key=f"group_input_seed_{ticket_id}",
                label_visibility='collapsed',
                placeholder='Enter group id',
            )
            selected_group_id = _safe_int(raw_group)

    # Load categories_tree if not provided
    if categories_tree is None:
        categories_tree = load_category_tree()
    
    category_payload = (
        _category_payload_from_path(
            recommended_category,
            similar_contexts=contexts,
            categories_tree=categories_tree
        ) 
        if recommended_category else None
    )
    target_group_update = (
        selected_group_id if selected_group_id is not None and selected_group_id != current_group_id else None
    )

    st.button(
        'Apply updates',
        key=f"apply_updates_{ticket_id}",
        use_container_width=True,
        disabled=(not category_payload and target_group_update is None),
        on_click=_queue_guidance_action,
        kwargs={
            'ticket_id': ticket_id,
            'category_payload': category_payload,
            'target_group': target_group_update,
        },
    )
            
def _build_current_ticket_payload(*, query_text: str, seed_meta: Optional[Dict[str, Any]], intent_tokens) -> dict:
    if seed_meta:
        subject = seed_meta.get("subject") or "Seeded Ticket"
        clean_desc = seed_meta.get("description_clean") or ""
        original_desc = seed_meta.get("description_raw") or clean_desc or query_text
        payload = {
            "ticket_id": seed_meta.get("ticket_id"),
            "subject": subject,
            "description_clean": clean_desc,
            "description_original": original_desc,
            "category": seed_meta.get("category"),
            "subcategory": seed_meta.get("subcategory"),
            "item": seed_meta.get("item"),
            "group_id": seed_meta.get("group_id"),
            "group_name": seed_meta.get("group_name"),
        }
    else:
        payload = {
            "ticket_id": None,
            "subject": "User Query",
            "description_clean": query_text,
            "description_original": query_text,
            "category": None,
            "subcategory": None,
            "item": None,
        }

    payload["detected_tokens"] = list(sorted(intent_tokens))
    return payload


def _infer_category_item(
    category: str,
    subcategory: str,
    similar_contexts: List[TicketContext],
    categories_tree: dict,
) -> Optional[str]:
    """
    Infer item when only category/subcategory provided.
    
    Tries in order:
    1. Most common item from similar tickets with matching category/subcategory
    2. Only item available in taxonomy for that category/subcategory
    3. Returns None if no inference possible (which is valid - not all categories have items)
    
    Args:
        category: Category name
        subcategory: Subcategory name
        similar_contexts: List of TicketContext objects from similar tickets
        categories_tree: Category taxonomy dict structure
        
    Returns:
        Inferred item name or None if cannot be inferred
    """
    from collections import Counter
    
    # Normalize for comparison (case-insensitive, strip whitespace)
    category_norm = (category or '').strip().lower()
    subcategory_norm = (subcategory or '').strip().lower()
    
    # Try 1: Find most common item from similar tickets with matching category/subcategory
    matching_items = []
    for ctx in similar_contexts:
        ctx_cat = (ctx.category or '').strip().lower()
        ctx_sub = (ctx.subcategory or '').strip().lower()
        ctx_item = (ctx.item or '').strip()
        
        if (ctx_cat == category_norm and 
            ctx_sub == subcategory_norm and 
            ctx_item):
            matching_items.append(ctx_item)
    
    if matching_items:
        most_common = Counter(matching_items).most_common(1)
        if most_common:
            return most_common[0][0]  # Return the item name (not the count)
    
    # Try 2: Check if only one item exists in taxonomy
    if categories_tree and category and subcategory:
        category_data = categories_tree.get(category, {})
        
        # Try exact match first
        subcategory_items = category_data.get(subcategory, [])
        
        # If no exact match, try case-insensitive match
        if not subcategory_items:
            for sub_key, items_list in category_data.items():
                if sub_key.strip().lower() == subcategory_norm:
                    subcategory_items = items_list
                    break
        
        # If only one item, use it
        if len(subcategory_items) == 1:
            return subcategory_items[0]
        
        # If multiple items, return None (don't guess)
        # If no items, return None (category may not have items)
    
    # No inference possible - return None (valid if item doesn't exist)
    return None


def _category_payload_from_path(
    path: List[str],
    similar_contexts: Optional[List[TicketContext]] = None,
    categories_tree: Optional[dict] = None,
) -> Dict[str, Optional[str]]:
    """
    Build category payload from path, inferring item if needed.
    
    Args:
        path: List of category path elements [category, subcategory, item?]
        similar_contexts: Optional list of TicketContext objects for inference
        categories_tree: Optional category taxonomy for inference
        
    Returns:
        Dictionary with category, sub_category, and optionally item_category
    """
    padded = list(path) + [None, None, None]
    category, subcategory, item = padded[:3]
    
    # Remove None values and strip whitespace
    category = category.strip() if category else None
    subcategory = subcategory.strip() if subcategory else None
    item = item.strip() if item else None
    
    payload: Dict[str, Optional[str]] = {}
    
    if category:
        payload["category"] = category
    if subcategory:
        payload["sub_category"] = subcategory
    
    # If item missing but we have category+subcategory, try to infer it
    if not item and category and subcategory:
        if similar_contexts is not None and categories_tree is not None:
            inferred_item = _infer_category_item(
                category, 
                subcategory, 
                similar_contexts, 
                categories_tree
            )
            if inferred_item:
                payload["item_category"] = inferred_item
                # Log the inference for debugging
                logger.info(
                    'Inferred category item',
                    extra={
                        'category': category,
                        'subcategory': subcategory,
                        'inferred_item': inferred_item
                    }
                )
    elif item:
        payload["item_category"] = item
    
    return payload


def _queue_guidance_action(
    *,
    ticket_id: Optional[int],
    category_payload: Optional[Dict[str, Optional[str]]],
    target_group: Optional[int],
) -> None:
    """Store pending guidance action to execute after Streamlit rerun."""
    if not ticket_id:
        return
    st.session_state['pending_guidance_action'] = {
        'ticket_id': ticket_id,
        'category_payload': dict(category_payload or {}),
        'target_group': target_group,
    }


def _process_pending_guidance_action(seed_tid: Optional[int]) -> None:
    """Execute any queued guidance updates immediately on rerun."""
    pending = st.session_state.pop('pending_guidance_action', None)
    if not pending:
        return

    ticket_id = pending.get('ticket_id') or seed_tid
    if not ticket_id:
        return

    update_kwargs: Dict[str, Any] = dict(pending.get('category_payload') or {})
    pending_group = pending.get('target_group')
    if pending_group is not None:
        update_kwargs['assignment_group_id'] = pending_group

    if not update_kwargs:
        return

    st.session_state['guidance_refresh_requested'] = True
    st.session_state['guidance_panel_open'] = True

    category_payload = pending.get('category_payload') or {}

    with st.spinner(f"Updating ticket #{ticket_id}..."):
        _update_ticket_fields(ticket_id, **update_kwargs)


def _update_ticket_fields(
    ticket_id: int,
    *,
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
    item_category: Optional[str] = None,
    # Accept legacy keyword names so older callers or cached state don't break.
    subcategory: Optional[str] = None,
    item: Optional[str] = None,
    assignment_group_id: Optional[int] = None,
) -> None:
    session = freshservice_session()
    update: Dict[str, Any] = {}
    if category is not None:
        update["category"] = category

    resolved_subcategory = sub_category if sub_category is not None else subcategory
    if resolved_subcategory is not None:
        update["sub_category"] = resolved_subcategory

    resolved_item = item_category if item_category is not None else item
    if resolved_item is not None:
        update["item_category"] = resolved_item
    if assignment_group_id is not None:
        group_numeric = _safe_int(assignment_group_id)
        if group_numeric is None:
            st.error("Assignment group must be numeric.")
            return
        update["group_id"] = group_numeric
        logger.info('update payload added group ticket=%s group_id=%s', ticket_id, group_numeric)
    if not update:
        st.info("Nothing to update.")
        return

    try:
        logger.info('updating ticket %s payload=%s', ticket_id, update)
        resp = session.put(
            f"{FRESHSERVICE_BASE_URL}/tickets/{ticket_id}",
            json={"ticket": update},
            timeout=REQUEST_TIMEOUT,
        )
        logger.info('update response ticket=%s status=%s body=%s', ticket_id, resp.status_code, resp.text[:200])

        response_data: Dict[str, Any] = {}
        try:
            response_data = resp.json()
        except ValueError:
            logger.warning('update response not json', extra={'ticket_id': ticket_id})

        if resp.status_code in (200, 201, 202):
            updated_ticket = response_data.get('ticket') if isinstance(response_data, dict) else None
            if updated_ticket:
                observed = {
                    'category': updated_ticket.get('category'),
                    'sub_category': updated_ticket.get('sub_category') or updated_ticket.get('subcategory'),
                    'item_category': updated_ticket.get('item_category') or updated_ticket.get('item'),
                    'group_id': updated_ticket.get('group_id'),
                }
                logger.info('update response fields ticket=%s observed=%s', ticket_id, observed)

                mismatch_msgs = []
                if 'category' in update and observed.get('category') != update['category']:
                    mismatch_msgs.append(f"category stayed '{observed.get('category')}'")
                if 'sub_category' in update and observed.get('sub_category') != update['sub_category']:
                    mismatch_msgs.append(f"sub_category stayed '{observed.get('sub_category')}'")
                if 'item_category' in update and observed.get('item_category') != update['item_category']:
                    mismatch_msgs.append(f"item_category stayed '{observed.get('item_category')}'")
                if 'group_id' in update and observed.get('group_id') != update['group_id']:
                    mismatch_msgs.append(f"group_id stayed '{observed.get('group_id')}'")

                if mismatch_msgs:
                    joined = ", ".join(mismatch_msgs)
                    st.warning(f"Freshservice accepted the request but fields did not change: {joined}")
                else:
                    st.success(f"Ticket #{ticket_id} updated successfully.")
            else:
                st.success(f"Ticket #{ticket_id} updated successfully.")
        else:
            st.error(f"Failed to update ticket {ticket_id}: {resp.status_code} {resp.text}")
    except Exception as exc:
        logger.exception('update ticket failed', extra={'ticket_id': ticket_id})
        st.error(f"Error updating ticket {ticket_id}: {exc}")


def _render_empty_state(require_token: bool, require_category: bool) -> None:
    st.warning("No tickets matched your current filters.")
    suggestions = []
    if require_token:
        suggestions.append("• Turn off **Require exact software terms**")
    if require_category:
        suggestions.append("• Turn off **Require same category**")
    if not suggestions:
        suggestions.append("• Broaden the search query or raise the distance threshold")

    st.markdown("\n".join(suggestions))

    cols = st.columns(2)
    if require_token:
        if cols[0].button("Allow other software terms"):
            st.session_state["require_token"] = False
            st.experimental_rerun()
    if require_category:
        if cols[1].button("Allow other categories"):
            st.session_state["require_category"] = False
            st.experimental_rerun()


# ----------------------------
# Sidebar controls
# ----------------------------
with st.sidebar:
    st.header("Search Controls")
    query_input = st.text_input(
        "Search (free text or a ticket ID)",
        value=st.session_state.get("query", ""),
        help="Enter text, or a ticket number like 4295",
        key="search_input"
    )

    # Store the current query
    st.session_state["query"] = query_input

    token_chip_container = st.container()
    with token_chip_container:
        st.caption("Detected tokens will appear here after you run a search.")

    clean_seed = st.checkbox(
        "Clean seed text",
        value=st.session_state.get("clean_seed", True),
        help="When using a ticket ID, remove signatures/reply tails before searching.",
        key="clean_seed"
    )

    use_ai_summary = st.checkbox(
        "🤖 AI-enhanced search",
        value=st.session_state.get("ai_summary", True),
        help="Use AI to create optimized summaries for better semantic matching with closed tickets. Disable for faster searches.",
        key="ai_summary"
    )

    require_token_match = st.checkbox(
        "Require exact software terms",
        value=st.session_state.get("require_token", False),
        help="Filter out tickets that do not mention high-signal software names detected in the query.",
        key="require_token"
    )

    seed_tid_preview = _detect_ticket_id(query_input)

    with st.expander("Advanced", expanded=False):
        debug_selected = st.checkbox(
            "🔧 Debug Mode",
            value=st.session_state.get("debug_mode", False),
            help="Show detailed error information and system diagnostics",
        )
        st.session_state.debug_mode = debug_selected
        show_desc_default = st.checkbox(
            "Show descriptions by default",
            value=st.session_state.get("show_descriptions", False),
            key="show_descriptions"
        )
        include_lower = st.checkbox(
            "Also show Similar/Related/Loose sections",
            value=st.session_state.get("include_lower", False),
            key="include_lower"
        )
        require_category_match = st.checkbox(
            "Require same category (seed)",
            value=st.session_state.get("require_category", False),
            help="Only keep results that share the seeded ticket's category path.",
            disabled=seed_tid_preview is None,
            key="require_category"
        )
    # Retrieve values from state if sidebar is collapsed
    show_desc_default = st.session_state.get("show_descriptions", False)
    include_lower = st.session_state.get("include_lower", False)
    require_category_match = st.session_state.get("require_category", False) and seed_tid_preview is not None

# Show system status in debug mode
if st.session_state.debug_mode:
    with st.sidebar.expander("📊 System Status"):
        try:
            display_system_status()
        except Exception as e:
            st.error(f"Failed to load system status: {e}")

# Build query text (free text OR seeded from a ticket)
seed_tid = seed_tid_preview
seed_meta: Optional[Dict[str, str]] = None

if seed_tid:
    # Let user exclude the seed ticket from results
    exclude_seed = st.sidebar.checkbox(
        "Exclude this ticket from results",
        value=st.session_state.get("exclude_seed", True),
        key="exclude_seed"
    )
    try:
        with st.spinner(f"Fetching ticket {seed_tid}..."):
            seed_text, seed_meta = build_seed_text_from_ticket(
                seed_tid, 
                clean=clean_seed,
                use_ai_summary=use_ai_summary
            )
        query_text = seed_text
    except Exception as e:
        st.sidebar.warning(f"Could not fetch ticket {seed_tid}: {e}")
        query_text = (query_input or "").strip()
else:
    exclude_seed = False
    query_text = (query_input or "").strip()

# Optional: show seed (cleaned vs original)
if seed_meta:
    # Show AI enhancement status
    ai_status = "🤖 AI-Enhanced" if seed_meta.get("ai_enhanced") == "yes" else "📝 Raw Text"
    
    with st.sidebar.expander(f"Seed text (from Freshservice) - {ai_status}", expanded=True):
        tabs = st.tabs(["Cleaned", "Original"])
        with tabs[0]:
            st.write(f"**Subject:** {seed_meta['subject'] or '—'}")
            st.caption("Cleaned text used for semantic search:")
            st.write(seed_meta.get("description_clean") or "—")
            if seed_meta.get("ai_enhanced") == "yes":
                st.caption("AI-enhanced search includes the summary shown below.")
        with tabs[1]:
            st.write(f"**Subject:** {seed_meta['subject'] or '—'}")
            st.caption("Original Freshservice description:")
            if seed_meta.get("description_html"):
                st.markdown(seed_meta.get("description_html") or "—", unsafe_allow_html=True)
            else:
                st.write(seed_meta.get("description_raw") or "—")

        # Show AI summary preview if available
        if seed_meta.get("ai_enhanced") == "yes" and "seed_text_preview" in seed_meta:
            st.markdown("**🤖 AI Summary Preview:**")
            st.caption(seed_meta["seed_text_preview"])


_process_pending_guidance_action(seed_tid)


if st.session_state.get('guidance_refresh_requested'):
    logger.info('guidance refresh requested, updating seed guidance cache')
    st.session_state.pop('guidance_refresh_requested', None)
    refreshed_meta = None
    try:
        refreshed_text, refreshed_meta = build_seed_text_from_ticket(
            seed_tid,
            clean=clean_seed,
            use_ai_summary=use_ai_summary,
        ) if seed_tid else (None, None)
    except Exception as refresh_err:
        logger.warning('Failed to refresh seed ticket after update: %s', refresh_err)
    if refreshed_meta:
        seed_meta = refreshed_meta

# Sync latest seed metadata into stored guidance so panels stay fresh
if seed_meta and 'ai_guidance' in st.session_state:
    stored = st.session_state.get('ai_guidance') or {}
    if stored.get('ticket_id') == seed_tid:
        stored['seed_meta'] = seed_meta
        st.session_state['ai_guidance'] = stored
elif st.session_state.get('guidance_refresh_requested'):
    st.session_state.pop('guidance_refresh_requested', None)

# ----------------------------
# Execute search
# ----------------------------
if not query_text:
    st.info("Enter a free-text query or a ticket ID to search.")
    st.stop()

# Perform search (no caching - always fresh results)
try:
    intent = extract_query_intent(query_text, seed_metadata=seed_meta)
    token_chip_container.empty()
    with token_chip_container:
        if intent.tokens:
            chips = "".join(
                f"<span class='chip chip-good'>{token}</span>" for token in sorted(intent.tokens)
            )
            st.markdown(f"**Detected tokens:**<br>{chips}", unsafe_allow_html=True)
        elif require_token_match:
            st.warning("No high-signal tokens detected in this query.")
        else:
            st.caption("Detected tokens will appear here after you run a search.")

    if require_category_match and not (seed_meta and any([seed_meta.get("category"), seed_meta.get("subcategory"), seed_meta.get("item")])):
        st.sidebar.warning("Category filtering requires a seeded ticket with category metadata.")

    all_results: List[Tuple[str, dict, float]] = retrieve_similar_tickets(
        query_text,
        top_n=None,
        max_distance=RELAXED_MAX_DISTANCE,
        intent=intent,
        require_token_match=require_token_match,
        require_category_match=require_category_match,
    )
    if not all_results:
        _render_empty_state(require_token_match, require_category_match)
        st.stop()
except Exception as e:
        st.error(f"❌ **Search failed**: {str(e)}")
        logger.error(f"Search error: {e}")
        logger.error(traceback.format_exc())
        
        if st.session_state.debug_mode:
            with st.expander("🔧 Debug Information"):
                st.error(f"Error: {str(e)}")
                st.code(traceback.format_exc())
        
        # Show system diagnostics in case of search failure
        st.warning("This might be due to a system configuration issue. Check diagnostics below:")
        try:
            display_system_status()
        except Exception as diag_error:
            st.error(f"Failed to load diagnostics: {diag_error}")
        
        st.stop()

# Optionally exclude the seed ticket itself
if seed_tid and exclude_seed:
    all_results = [(d, m, dist) for (d, m, dist) in all_results if int(m.get("ticket_id") or -1) != seed_tid]

# Sort by distance (defensive)
all_results.sort(key=lambda x: x[2])

# Bucket for UX
buckets = _bucket_by_percentile(all_results)
most = buckets["most"]
similar = buckets["similar"]
related = buckets["related"]
loose = buckets["loose"]

# ----------------------------
# Summary (computed from MOST SIMILAR only)
# ----------------------------
st.subheader("Summary")

left, a_col, g_col, p_col = st.columns([1.0, 1.4, 1.4, 2.2])

with left:
    st.markdown("<div class='label'>Total results</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='kpi'>{len(all_results)}</div>", unsafe_allow_html=True)
    st.caption(f"(distance ≤ {RELAXED_MAX_DISTANCE})")

ms_summary = summarize(most)

with a_col:
    st.markdown("**Top Agents (Most Similar)**")
    if ms_summary["top_agents"]:
        for a in ms_summary["top_agents"]:
            st.write(f"- {a['name']} ({a['pct']}%)")
    else:
        st.write("—")

with g_col:
    st.markdown("**Top Groups (Most Similar)**")
    if ms_summary["top_groups"]:
        for g in ms_summary["top_groups"]:
            st.write(f"- {g['name']} ({g['pct']}%)")
    else:
        st.write("—")

with p_col:
    st.markdown("**Top Category Paths (Most Similar)**")
    if ms_summary["top_paths"]:
        for p in ms_summary["top_paths"]:
            st.write(f"- {p['path']} ({p['pct']}%)")
    else:
        st.write("—")

st.divider()

# ----------------------------
# AI Guidance
# ----------------------------
guidance_key = f"{query_text}|{sorted(intent.tokens)}|{require_token_match}|{require_category_match}|{seed_tid}"
stored_guidance = st.session_state.get("ai_guidance")

if not stored_guidance:
    st.session_state['guidance_panel_open'] = False
elif stored_guidance.get("key") != guidance_key:
    st.session_state['guidance_panel_open'] = False

st.subheader("AI Guidance")
controls_col, info_col = st.columns([0.3, 0.7])
with controls_col:
    run_guidance = st.button("✨ Generate Guidance", use_container_width=True)
with info_col:
    st.caption("Uses similar tickets and notes to recommend next steps, category, and assignment group.")

if run_guidance:
    try:
        with st.spinner("Consulting AI and analyzing similar tickets..."):
            logger.info('guidance button pressed', extra={'ticket_id': seed_tid, 'seed_meta_keys': sorted((seed_meta or {}).keys())})
            similar_contexts = gather_ticket_contexts(most)
            categories_tree = load_category_tree()
            current_payload = _build_current_ticket_payload(
                query_text=query_text,
                seed_meta=seed_meta,
                intent_tokens=intent.tokens,
            )
            guidance = generate_guidance(
                current_ticket=current_payload,
                similar_contexts=similar_contexts,
                categories_tree=categories_tree,
                detected_tokens=intent.tokens,
            )
            st.session_state["ai_guidance"] = {
                "key": guidance_key,
                "payload": guidance,
                "contexts": similar_contexts,
                "categories_tree": categories_tree,
                "ticket_id": seed_tid,
                "seed_meta": seed_meta,
            }
            st.session_state['guidance_panel_open'] = True
    except Exception as guidance_error:
        st.error(f"Failed to generate guidance: {guidance_error}")

stored_guidance = st.session_state.get("ai_guidance")
guidance_matches = stored_guidance and stored_guidance.get("key") == guidance_key

if guidance_matches:
    st.session_state['guidance_panel_open'] = True
    _render_guidance(
        stored_guidance["payload"],
        stored_guidance.get("contexts") or [],
        stored_guidance.get("ticket_id"),
        stored_guidance.get("seed_meta"),
        stored_guidance.get("categories_tree"),
    )
elif st.session_state.get('guidance_panel_open'):
    st.info("Guidance is out of date for this ticket. Generate new recommendations.")
else:
    st.caption("Generate guidance to see recommended actions and quick updates.")

# ----------------------------
# Results
# ----------------------------
st.subheader("Most Similar")
if not most:
    st.info("No highly similar tickets found. Try broadening your query.")
else:
    for doc, m, dist in most[:SEARCH_MAX_DISPLAY]:
        _render_card(doc, m, dist, show_desc_default=show_desc_default)

# Other sections collapsed by default; title only until expanded
if include_lower:
    with st.expander(f"Similar ({len(similar)})", expanded=False):
        for doc, m, dist in similar:
            _render_card(doc, m, dist, show_desc_default=False)

    with st.expander(f"Related ({len(related)})", expanded=False):
        for doc, m, dist in related:
            _render_card(doc, m, dist, show_desc_default=False)

    with st.expander(f"Loose ({len(loose)})", expanded=False):
        for doc, m, dist in loose:
            _render_card(doc, m, dist, show_desc_default=False)
else:
    # Show counts only
    cols = st.columns(3)
    cols[0].markdown(f"**Similar:** {len(similar)}")
    cols[1].markdown(f"**Related:** {len(related)}")
    cols[2].markdown(f"**Loose:** {len(loose)}")

# Auto-clear search after results are displayed (like a normal search box)
# This ensures the next search works immediately without caching issues
if "search_results" in st.session_state:
    del st.session_state["search_results"]
if "search_cache_key" in st.session_state:
    del st.session_state["search_cache_key"]
