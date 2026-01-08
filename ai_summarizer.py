# =========================
# File: ai_summarizer.py
# AI-powered ticket summarization for better semantic search
# =========================

import logging
from typing import Optional
from dotenv import load_dotenv

from improved_ai_prompt import (
    create_enhanced_system_message,
    create_enhanced_ticket_summary_prompt,
    create_enhanced_search_query_prompt,
    create_search_optimizer_system_message,
)

# Load environment early so config sees env vars
load_dotenv('api.env') or load_dotenv()

from config import OPENAI_API_KEY, OPENAI_SUMMARIZER_MODEL

logger = logging.getLogger(__name__)

DEFAULT_SUMMARIZER_MODEL = OPENAI_SUMMARIZER_MODEL

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
        import openai
        
        # Set up OpenAI
        openai.api_key = OPENAI_API_KEY
        
        system_message = create_enhanced_system_message()
        prompt = create_enhanced_ticket_summary_prompt(subject, description, ticket_id=ticket_id)

        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Add ticket context if provided
        if ticket_id:
            summary = f"[Ticket {ticket_id}] {summary}"
        
        logger.info(f"Created AI summary for ticket: {ticket_id or 'unknown'}")
        return summary
        
    except Exception as e:
        logger.error(f"Failed to create AI summary: {e}")
        # Fallback to original text if AI fails
        return f"{subject}\n\n{description}"

def enhance_search_query_with_ai(
    query_text: str,
    ticket_id: Optional[int] = None,
    *,
    model: str = DEFAULT_SUMMARIZER_MODEL,
) -> str:
    """
    Enhance a search query using AI to improve semantic matching.
    
    Args:
        query_text: Original search text
        ticket_id: Optional ticket ID for context
        
    Returns:
        AI-enhanced search query
    """
    try:
        import openai
        
        # Set up OpenAI
        openai.api_key = OPENAI_API_KEY
        
        system_message = create_search_optimizer_system_message()
        prompt = create_enhanced_search_query_prompt(query_text)

        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        enhanced_query = response.choices[0].message.content.strip()
        
        logger.info(f"Enhanced search query with AI")
        return enhanced_query
        
    except Exception as e:
        logger.error(f"Failed to enhance search query: {e}")
        # Fallback to original query if AI fails
        return query_text

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

if __name__ == "__main__":
    # Test the AI summarization
    test_subject = "Revit desktop connector is acting up"
    test_description = "I can't open my desktop connector for some reason. I think it's causing issues with tasks I need to complete."
    
    print("🧪 Testing AI Summarization")
    print("=" * 40)
    print(f"Original Subject: {test_subject}")
    print(f"Original Description: {test_description}")
    print()
    
    try:
        summary = create_ticket_summary(test_subject, test_description, 6511)
        print(f"AI Summary: {summary}")
        print()
        
        enhanced_query = enhance_search_query_with_ai(test_subject + " " + test_description)
        print(f"Enhanced Query: {enhanced_query}")
        print()
        
        combined = create_comprehensive_ticket_embedding_text(test_subject, test_description, 6511)
        print(f"Combined Text (first 200 chars): {combined[:200]}...")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure OPENAI_API_KEY is set in your environment")
