# =========================
# File: config.py
# =========================
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import openai

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
# OpenAI (used by error extractor; embeddings too)
# ---------------------------------------
OPENAI_API_KEY = _getenv("OPENAI_API_KEY", required=True).strip()
OPENAI_EMBEDDING_MODEL = _getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
OPENAI_GUIDANCE_MODEL = _getenv("OPENAI_GUIDANCE_MODEL", "gpt-4o-mini").strip()
OPENAI_SUMMARIZER_MODEL = _getenv("OPENAI_SUMMARIZER_MODEL", _getenv("OPENAI_GUIDANCE_MODEL", "gpt-4o-mini")).strip()


# ---------------------------------------
# Chroma config
# ---------------------------------------
CHROMA_DB_PATH = _getenv("CHROMA_DB_PATH", "./chroma_db").strip().strip('"')
CHROMA_COLLECTION_NAME = _getenv("CHROMA_COLLECTION_NAME", "freshservice_core").strip()


# ---------------------------------------
# Knobs (ingest/search)
# ---------------------------------------
INGEST_MAX_TOKENS = int(_getenv("INGEST_MAX_TOKENS", "3000"))
INGEST_STATUS_CODE = int(_getenv("INGEST_STATUS_CODE", "5"))           # 5 = Closed
SEARCH_MAX_DISTANCE = float(_getenv("SEARCH_MAX_DISTANCE", "0.55"))    # CLI/default knob
SEARCH_MAX_DISPLAY = int(_getenv("SEARCH_MAX_DISPLAY", "10"))          # how many to show


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


def openai_client():
    """OpenAI SDK client (used by extract_error_messages.py)."""
    openai.api_key = OPENAI_API_KEY
    return openai


def embedding_function() -> OpenAIEmbeddingFunction:
    """
    Embedding function for Chroma collections.
    Uses OpenAI's text-embedding-3-small by default (cost-effective).
    """
    return OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=OPENAI_EMBEDDING_MODEL)


def chroma_collection(name: Optional[str] = None):
    """
    Return a persistent Chroma collection at CHROMA_DB_PATH.
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
