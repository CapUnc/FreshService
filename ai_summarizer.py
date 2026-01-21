# =========================
# File: ai_summarizer.py
# AI-powered ticket summarization for better semantic search
# =========================

import logging
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

from improved_ai_prompt import (
    create_enhanced_system_message,
    create_enhanced_ticket_summary_prompt,
)

# Load environment early so config sees env vars
load_dotenv('api.env') or load_dotenv()

from config import OPENAI_API_KEY, OPENAI_SUMMARIZER_MODEL

logger = logging.getLogger(__name__)

DEFAULT_SUMMARIZER_MODEL = OPENAI_SUMMARIZER_MODEL


@lru_cache(maxsize=512)
def _cached_ticket_summary(
    subject: str,
    description: str,
    ticket_id: Optional[int],
    model: str,
) -> str:
    import openai

    openai.api_key = OPENAI_API_KEY

    system_message = create_enhanced_system_message()
    prompt = create_enhanced_ticket_summary_prompt(subject, description, ticket_id=ticket_id)

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        max_tokens=150,
        temperature=0.3,
    )

    summary = response.choices[0].message.content.strip()

    if ticket_id:
        summary = f"[Ticket {ticket_id}] {summary}"

    return summary

def create_ticket_summary(
    subject: str,
    description: str,
    ticket_id: Optional[int] = None,
    *,
    model: str = DEFAULT_SUMMARIZER_MODEL,
) -> str:
    """
    Create an AI-powered summary of a ticket for better semantic search.
    
    Args:
        subject: Ticket subject
        description: Ticket description (cleaned)
        ticket_id: Optional ticket ID for context
        
    Returns:
        AI-generated summary optimized for semantic search
    """
    try:
        summary = _cached_ticket_summary(subject, description, ticket_id, model)
        logger.info("Created AI summary for ticket: %s", ticket_id or "unknown")
        return summary
    except Exception as e:
        logger.error(f"Failed to create AI summary: {e}")
        # Fallback to original text if AI fails
        return f"{subject}\n\n{description}"

def create_comprehensive_ticket_embedding_text(
    subject: str,
    description: str,
    ticket_id: Optional[int] = None,
    *,
    model: str = DEFAULT_SUMMARIZER_MODEL,
) -> str:
    """
    Create comprehensive text for embedding that combines original content with AI summary.
    
    Args:
        subject: Ticket subject
        description: Ticket description
        ticket_id: Optional ticket ID
        
    Returns:
        Combined text optimized for embedding
    """
    try:
        # Create AI summary
        ai_summary = create_ticket_summary(subject, description, ticket_id, model=model)
        
        # Combine with original content
        combined_text = f"{ai_summary}\n\n---\n\nOriginal:\n{subject}\n\n{description}"
        
        return combined_text
        
    except Exception as e:
        logger.error(f"Failed to create comprehensive embedding text: {e}")
        # Fallback to original text
        return f"{subject}\n\n{description}"
