# =========================
# File: config.py
# =========================
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# ---------------------------------------
# Load environment (api.env preferred)
# ---------------------------------------
# Try api.env first (your project standard), then fallback to .env
load_dotenv("api.env") or load_dotenv()


# ---------------------------------------
# Env helpers
# ---------------------------------------
def _getenv(key: str, default: Optional[str] = None, *, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {key}")
    return val if val is not None else ""


# ---------------------------------------
# Freshservice config
# ---------------------------------------
def normalise_freshservice_domain(domain: str) -> str:
    """Normalize a Freshservice domain to its subdomain form."""
    cleaned = (domain or "").strip().lower()
    if not cleaned:
        raise ValueError("Freshservice domain is required.")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    cleaned = cleaned.split("/", 1)[0]
    if cleaned.endswith(".freshservice.com"):
        cleaned = cleaned[: -len(".freshservice.com")]
    cleaned = cleaned.strip(".")
    if not cleaned:
        raise ValueError("Freshservice domain is invalid.")
    return cleaned


FRESHSERVICE_DOMAIN = normalise_freshservice_domain(
    _getenv("FRESHSERVICE_DOMAIN", required=True)
)
FRESHSERVICE_API_KEY = _getenv("FRESHSERVICE_API_KEY", required=True).strip()
FRESHSERVICE_BASE_URL = f"https://{FRESHSERVICE_DOMAIN}.freshservice.com/api/v2"

REQUEST_TIMEOUT = float(_getenv("REQUEST_TIMEOUT_SECONDS", "30"))   # seconds
RATE_LIMIT_SLEEP = float(_getenv("RATE_LIMIT_SLEEP_SECONDS", "60")) # seconds


# ---------------------------------------
# OpenAI (used for embeddings and AI features)
# ---------------------------------------
OPENAI_API_KEY = _getenv("OPENAI_API_KEY", required=True).strip()
OPENAI_EMBEDDING_MODEL = _getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
OPENAI_GUIDANCE_MODEL = _getenv("OPENAI_GUIDANCE_MODEL", "gpt-4o-mini").strip()
OPENAI_SUMMARIZER_MODEL = _getenv("OPENAI_SUMMARIZER_MODEL", _getenv("OPENAI_GUIDANCE_MODEL", "gpt-4o-mini")).strip()
# Comma-separated list of models offered in the in-app picker (blank => sensible default).
OPENAI_AVAILABLE_MODELS = _getenv("OPENAI_AVAILABLE_MODELS", "").strip()


# ---------------------------------------
# Chroma config
# ---------------------------------------
CHROMA_DB_PATH = _getenv("CHROMA_DB_PATH", "./chroma_db").strip().strip('"')
CHROMA_COLLECTION_NAME = _getenv("CHROMA_COLLECTION_NAME", "nexus_tickets").strip()


# ---------------------------------------
# Knobs (ingest/search)
# ---------------------------------------
INGEST_MAX_TOKENS = int(_getenv("INGEST_MAX_TOKENS", "3000"))
INGEST_STATUS_CODE = int(_getenv("INGEST_STATUS_CODE", "5"))           # 5 = Closed
SEARCH_MAX_DISTANCE = float(_getenv("SEARCH_MAX_DISTANCE", "0.55"))    # CLI/default knob
SEARCH_MAX_DISPLAY = int(_getenv("SEARCH_MAX_DISPLAY", "10"))          # how many to show
MAX_SIMILAR_TICKETS = int(_getenv("MAX_SIMILAR_TICKETS", "5"))          # guidance cap


# ---------------------------------------
# Factories / clients
# ---------------------------------------
def freshservice_session() -> Session:
    """
    Freshservice session with API key auth.
    We use HTTP Basic with the API key as username, 'X' as password.
    """
    s = Session()
    s.auth = HTTPBasicAuth(FRESHSERVICE_API_KEY, "X")
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s


@lru_cache(maxsize=1)
def shared_freshservice_session() -> Session:
    """Process-wide reusable Freshservice session.

    Reuses one connection pool (HTTP keep-alive) across the many small
    ticket/agent/group lookups performed during search and ingestion. requests'
    underlying urllib3 pool is thread-safe, so this is safe to share across the
    context-fetch thread pool in search_context.
    """
    return freshservice_session()


def embedding_function() -> OpenAIEmbeddingFunction:
    """
    Embedding function for Chroma collections.
    Uses OpenAI's text-embedding-3-small by default (cost-effective).
    """
    return OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=OPENAI_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def openai_client():
    """Return a shared OpenAI client (modern >=1.x SDK), created once and reused."""
    from openai import OpenAI

    return OpenAI(api_key=OPENAI_API_KEY)


def available_models() -> list[str]:
    """Models offered in the in-app picker.

    Sourced from the comma-separated OPENAI_AVAILABLE_MODELS env var, or a sensible
    default list. The configured guidance model is always included and listed first.
    """
    if OPENAI_AVAILABLE_MODELS:
        models = [m.strip() for m in OPENAI_AVAILABLE_MODELS.split(",") if m.strip()]
    else:
        models = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]

    ordered = [OPENAI_GUIDANCE_MODEL, *models]
    seen: set[str] = set()
    unique: list[str] = []
    for name in ordered:
        if name and name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


@lru_cache(maxsize=4)
def chroma_collection(name: Optional[str] = None):
    """
    Return a persistent Chroma collection at CHROMA_DB_PATH.
    Cached per name so the client + embedding function are built once and reused
    across searches (previously rebuilt on every query).
    If it doesn't exist yet, create it with the configured embedding function.
    """
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    try:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)  # ensure path exists
        logger.info(f"Connecting to ChromaDB at: {CHROMA_DB_PATH}")
        
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        coll_name = name or CHROMA_COLLECTION_NAME
        
        logger.info(f"Accessing collection: {coll_name}")
        
        try:
            # Chroma 0.5.x provides get_or_create_collection
            collection = client.get_or_create_collection(
                name=coll_name,
                embedding_function=embedding_function(),
            )
            logger.info("Successfully connected to ChromaDB collection")
            return collection
        except AttributeError:
            # Fallback if your installed version lacks get_or_create_collection
            logger.info("Using fallback collection access method")
            try:
                collection = client.get_collection(
                    name=coll_name,
                    embedding_function=embedding_function(),
                )
                logger.info("Successfully accessed existing ChromaDB collection")
                return collection
            except chromadb.errors.NotFoundError:
                logger.info("Creating new ChromaDB collection")
                collection = client.create_collection(
                    name=coll_name,
                    embedding_function=embedding_function(),
                )
                logger.info("Successfully created new ChromaDB collection")
                return collection
                
    except Exception as e:
        error_msg = f"ChromaDB connection failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Provide helpful error messages
        if "ImportError" in str(type(e)):
            raise RuntimeError(
                "ChromaDB import failed. This is usually due to version compatibility issues. "
                "Try running: pip install chromadb==0.4.22"
            ) from e
        elif "Permission denied" in str(e):
            raise RuntimeError(
                f"Permission denied accessing ChromaDB path: {CHROMA_DB_PATH}. "
                "Check file permissions or try a different path."
            ) from e
        elif "No space left" in str(e):
            raise RuntimeError(
                "No space left on device. Free up disk space and try again."
            ) from e
        else:
            raise RuntimeError(
                f"ChromaDB connection failed: {str(e)}. "
                "Check your configuration and ensure the database path is accessible."
            ) from e

# ---------------------------------------
# Small helpers (single definitions)
# ---------------------------------------
def get_ticket_url(ticket_id: int | str) -> str:
    """Convenience helper to link to a Helpdesk ticket detail page."""
    try:
        tid = int(ticket_id)
    except Exception:
        tid = ticket_id  # leave as-is if not an int
    return f"https://{FRESHSERVICE_DOMAIN}.freshservice.com/helpdesk/tickets/{tid}"


def get_distance_threshold() -> float:
    """Expose the default search cutoff for CLI tools."""
    return float(SEARCH_MAX_DISTANCE)
