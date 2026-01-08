"""Generate AI guidance for agents based on similar Freshservice tickets."""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass
from typing import List, Sequence

import openai

from config import OPENAI_API_KEY, OPENAI_GUIDANCE_MODEL
from search_context import TicketContext
from improved_ai_prompt import (
    create_ai_guidance_prompt_with_sources,
    create_guidance_system_message,
)


DEFAULT_GUIDANCE_MODEL = OPENAI_GUIDANCE_MODEL
logger = logging.getLogger(__name__)


@dataclass
class AIGuidance:
    agent_markdown: str
    recommended_category: List[str] | None
    recommended_group: str | None
    confidence: str | None
    supporting_tickets: List[dict]


def generate_guidance(
    *,
    current_ticket: dict,
    similar_contexts: Sequence[TicketContext],
    categories_tree: dict,
    detected_tokens: Sequence[str],
    model: str = DEFAULT_GUIDANCE_MODEL,
    temperature: float = 0.2,
) -> AIGuidance:
    """Call OpenAI to produce recommended next steps and routing guidance.

    Steps:
      1. Summarise the similar tickets (including private notes when present).
      2. Construct a structured JSON payload with the current ticket, category
         taxonomy, detected tokens, and candidate assignment groups.
      3. Ask the guidance model for a JSON response that includes coaching,
         routing, confidence, and supporting ticket citations.
      4. Parse the reply; if parsing fails, fall back to returning the raw text
         so the UI can still surface something.
    """

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing; cannot generate guidance")

    assignment_groups = sorted(
        {
            ctx.group_name
            for ctx in similar_contexts
            if ctx.group_name
        }
    )

    similar_ticket_entries = []
    for ctx in similar_contexts:
        category_path_parts = [part for part in (ctx.category, ctx.subcategory, ctx.item) if part]
        category_path = " → ".join(category_path_parts) if category_path_parts else "Unknown"

        resolution_note = next((note.body for note in ctx.notes if note.is_private and note.body), None)
        if not resolution_note:
            resolution_note = next((note.body for note in ctx.notes if note.body), None)

        similar_ticket_entries.append(
            {
                "ticket_id": ctx.ticket_id,
                "subject": ctx.subject or "",
                "resolution": resolution_note or "No resolution provided",
                "category": category_path,
                "assignment_group": ctx.group_name or "Unknown",
            }
        )

    current_ticket_details = {
        "subject": current_ticket.get("subject") or "Unknown subject",
        "description": current_ticket.get("description_clean")
        or current_ticket.get("description_original")
        or "",
    }
    if current_ticket.get("ticket_id"):
        current_ticket_details["ticket_id"] = current_ticket.get("ticket_id")

    prompt_text = create_ai_guidance_prompt_with_sources(
        similar_tickets=similar_ticket_entries,
        current_ticket=current_ticket_details,
        detected_tokens=list(detected_tokens),
        category_taxonomy=categories_tree,
        assignment_groups=assignment_groups,
    )

    system_prompt = create_guidance_system_message()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_text},
    ]

    if os.getenv("LOG_GUIDANCE_PROMPT") == "1":
        prompt_logger = logging.getLogger("guidance_prompt")
        if not getattr(prompt_logger, "_freshservice_handler", None):
            handler = logging.FileHandler("freshservice_debug.log")
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            prompt_logger.addHandler(handler)
            prompt_logger.setLevel(logging.INFO)
            prompt_logger._freshservice_handler = handler  # type: ignore[attr-defined]

        prompt_logger.info("=== OpenAI guidance request ===")
        prompt_logger.info("System prompt: %s", system_prompt)
        prompt_logger.info("User prompt: %s", prompt_text)

    # Debug logging for prompt verification
    if os.getenv("LOG_GUIDANCE_PROMPT") == "1":
        logger.info("=== OpenAI guidance request ===")
        logger.info("System: %s", system_prompt)
        logger.info("User prompt: %s", prompt_text)

    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
    except Exception as exc:
        logger.error("OpenAI guidance call failed: %s", exc)
        raise



    content = response.choices[0].message["content"].strip()
    parsed = None
    if content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # Some responses may include explanatory text around JSON. Attempt to
            # recover the largest JSON-looking block before giving up.
            trimmed = content.strip()
            start = trimmed.find('{')
            end = trimmed.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = trimmed[start : end + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    logger.warning("OpenAI guidance JSON parse failed; returning raw content")
            else:
                logger.warning("OpenAI guidance response missing JSON block; returning raw content")

    if not isinstance(parsed, dict):
        return AIGuidance(
            agent_markdown=content,
            recommended_category=None,
            recommended_group=None,
            confidence=None,
            supporting_tickets=[],
        )

    category_path = parsed.get("recommended_category_path")
    if isinstance(category_path, str):
        category_path = [category_path]

    return AIGuidance(
        agent_markdown=parsed.get("agent_response_markdown", content),
        recommended_category=category_path,
        recommended_group=parsed.get("recommended_assignment_group"),
        confidence=parsed.get("confidence"),
        supporting_tickets=parsed.get("supporting_tickets", []),
    )
