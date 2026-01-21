# =========================
# File: agent_resolver.py
# Unified agent and group name resolution with caching
# =========================
from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Optional

from config import (
    freshservice_session,
    FRESHSERVICE_BASE_URL,
    REQUEST_TIMEOUT,
    RATE_LIMIT_SLEEP,
)

logger = logging.getLogger(__name__)


def _name_from_agent_payload(payload: dict) -> str:
    """
    Extract agent name from API payload.
    Prefer agent-level first/last, then agent.name, then contact.name, then contact.first/last.
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


@lru_cache(maxsize=8192)
def get_agent_name(agent_id: Optional[int]) -> str:
    """
    Get agent name by ID with caching and retry logic.
    
    Args:
        agent_id: Agent ID (can be None for unassigned)
        
    Returns:
        Agent name or "Unassigned" if None, "Unknown" on error
    """
    if agent_id is None:
        return "Unassigned"
    
    if not isinstance(agent_id, int):
        try:
            agent_id = int(agent_id)
        except (ValueError, TypeError):
            return "Unassigned"
    
    session = freshservice_session()
    url = f"{FRESHSERVICE_BASE_URL}/agents/{agent_id}"
    attempts = 3
    
    for attempt in range(attempts):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 503):
                if attempt < attempts - 1:
                    wait = RATE_LIMIT_SLEEP * (attempt + 1)
                    logger.debug(f"[rate] agent lookup {agent_id} -> {r.status_code}; sleeping {wait:.2f}s")
                    time.sleep(wait)
                    continue
            
            r.raise_for_status()
            return _name_from_agent_payload(r.json() or {})
            
        except Exception as exc:
            if attempt < attempts - 1:
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logger.debug(f"[warn] agent lookup {agent_id} failed ({exc}); retrying in {wait:.2f}s")
                time.sleep(wait)
            else:
                logger.warning(f"[warn] agent lookup {agent_id} failed; using 'Unknown'")
    
    return "Unknown"


@lru_cache(maxsize=4096)
def get_group_name(group_id: Optional[int]) -> str:
    """
    Get group name by ID with caching and retry logic.
    
    Args:
        group_id: Group ID (can be None)
        
    Returns:
        Group name or "Unknown" on error/None
    """
    if group_id is None:
        return "Unknown"
    
    if not isinstance(group_id, int):
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return "Unknown"
    
    session = freshservice_session()
    url = f"{FRESHSERVICE_BASE_URL}/groups/{group_id}"
    attempts = 3
    
    for attempt in range(attempts):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 503):
                if attempt < attempts - 1:
                    wait = RATE_LIMIT_SLEEP * (attempt + 1)
                    logger.debug(f"[rate] group lookup {group_id} -> {r.status_code}; sleeping {wait:.2f}s")
                    time.sleep(wait)
                    continue
            
            r.raise_for_status()
            name = ((r.json() or {}).get("group", {}) or {}).get("name", "")
            return (name or "").strip() or "Unknown"
            
        except Exception as exc:
            if attempt < attempts - 1:
                wait = RATE_LIMIT_SLEEP * (attempt + 1)
                logger.debug(f"[warn] group lookup {group_id} failed ({exc}); retrying in {wait:.2f}s")
                time.sleep(wait)
            else:
                logger.warning(f"[warn] group lookup {group_id} failed; using 'Unknown'")
    
    return "Unknown"
