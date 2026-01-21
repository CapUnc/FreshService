"""Tests for AI summarizer functionality."""

import os
from ai_summarizer import (
    create_ticket_summary,
    create_comprehensive_ticket_embedding_text,
)


def test_ai_summarization() -> None:
    """Test the AI summarization functionality."""
    # Skip if API key not available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set, skipping AI summarization tests")
        return
    
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
        
        combined = create_comprehensive_ticket_embedding_text(test_subject, test_description, 6511)
        print(f"Combined Text (first 200 chars): {combined[:200]}...")
        print()
        print("✅ AI summarization tests passed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure OPENAI_API_KEY is set in your environment")
        raise


if __name__ == "__main__":
    test_ai_summarization()
