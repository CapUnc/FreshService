# =========================
# File: text_cleaning.py
# =========================
"""
Shared text cleaning utilities used by both embedding (freshservice.py)
and searching (app/search_tickets). Conservative: only removes obvious
reply history, confidentiality footers, and signature blocks.
"""

from __future__ import annotations
import re
from typing import Optional

# --- Normalization ---
def _normalize_ws(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)       # 3+ blank lines -> 2
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return s.strip()

# --- Cutting reply history ---
_REPLY_LINE_PATTERNS = [
    re.compile(r"^\s*On .+ wrote:\s*$", re.I),
    re.compile(r"^\s*-{5,}\s*Original Message\s*-{5,}\s*$", re.I),
    re.compile(r"^\s*From:\s+.+$", re.I),  # will confirm with nearby headers
]

def _looks_like_header_bundle(lines, start) -> bool:
    window = "\n".join(lines[start:start+6]).lower()
    hits = sum(k in window for k in ("from:", "sent:", "to:", "subject:"))
    return hits >= 3

def _cut_reply_history(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if any(p.search(line) for p in _REPLY_LINE_PATTERNS):
            if line.lower().startswith("from:") and not _looks_like_header_bundle(lines, i):
                continue
            return "\n".join(lines[:i]).rstrip()
    return text

# --- Confidential/legal footer ---
_CONFIDENTIAL = re.compile(
    r"(confidential|privileged|intended only for|unauthorized|disclosure|legal disclaimer)",
    re.I,
)

def _strip_confidentiality(text: str) -> str:
    m = _CONFIDENTIAL.search(text or "")
    if m:
        return (text or "")[:m.start()].rstrip()
    return text

# --- Signature detection (conservative) ---
_SIG_SIGNOFF = re.compile(r"^\s*(thanks|thank you|regards|best|sincerely|cheers)[,]?\s*$", re.I)
_CONTACTISH = re.compile(
    r"(@|\bhttps?://|\bwww\.|tel[:\s]|phone|cell|mobile|fax|\.com\b|llc\b|inc\b|cto\b|ceo\b|manager\b|director\b)",
    re.I,
)

def _strip_signature_block(text: str) -> str:
    lines = (text or "").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if _SIG_SIGNOFF.match(lines[i].strip()):
            tail = lines[i+1:i+9]
            contactish = sum(1 for ln in tail if _CONTACTISH.search(ln or ""))
            if contactish >= 2:
                return "\n".join(lines[:i]).rstrip()
    return text

# --- HTML to text conversion ---
def html_to_text(html: Optional[str]) -> str:
    """Convert HTML to plain text, handling None/empty input."""
    if not html:
        return ""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


# --- Public API ---
def clean_description(raw: str) -> str:
    """Conservative clean; subject should not be passed here."""
    s = _normalize_ws(raw or "")
    s = _cut_reply_history(s)
    s = _strip_confidentiality(s)
    s = _strip_signature_block(s)
    s = _normalize_ws(s)
    return s