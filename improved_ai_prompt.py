"""Prompt builders for AI summarization and guidance flows.

This module centralises the prompt text used by the semantic search system so the
Streamlit app, CLI, and background jobs share a consistent set of
instructions.
"""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Sequence


def _normalise_tokens(tokens: Iterable[str]) -> List[str]:
    """Return unique, sorted tokens with whitespace trimmed."""

    cleaned = {token.strip() for token in tokens or [] if token and token.strip()}
    return sorted(cleaned)


def create_enhanced_system_message() -> str:
    """System directive for ticket summarisation prompts."""

    return dedent(
        """
        You are an AI assistant helping the Freshservice help desk summarise
        tickets. Produce concise, factual summaries (one to three sentences)
        that highlight the core issue, key systems or software, symptoms or
        error messages, and any troubleshooting already performed. Do not invent
        actions or outcomes that were not explicitly mentioned. Avoid bullet
        lists; respond with a compact paragraph of plain language suitable for
        semantic search.
        """
    ).strip()


def create_search_optimizer_system_message() -> str:
    """System directive for search query optimisation prompts."""

    return dedent(
        """
        You are an IT service desk search optimiser. Rewrite the user's query so
        that it captures the important software names, symptoms, and relevant
        terminology while removing filler text. Expand abbreviations where
        helpful, include common synonyms, and keep the result to a single line
        of plain text. Return only the improved query with no explanations or
        additional formatting.
        """
    ).strip()


def create_enhanced_ticket_summary_prompt(
    subject: str,
    description: str,
    *,
    ticket_id: int | None = None,
) -> str:
    """Build the user prompt for generating an AI ticket summary."""

    ticket_label = f"Ticket {ticket_id}" if ticket_id else "Ticket"
    subject_text = subject or "(no subject provided)"
    description_text = description.strip() if description else "(no description provided)"

    return dedent(
        f"""
        Summarise the following Freshservice {ticket_label} in at most three
        sentences. Focus on:
          • Primary problem / goal
          • Systems or software mentioned
          • Key error messages or symptoms
          • Troubleshooting already attempted (if any)
        Do not add remediation steps that are not in the text.

        Subject: {subject_text}
        Description:
        ---
        {description_text}
        ---

        Respond with a concise paragraph suitable for semantic similarity search.
        """
    ).strip()


def create_enhanced_search_query_prompt(query_text: str) -> str:
    """Construct the user prompt for optimising a search query."""

    original = query_text.strip() if query_text else "(empty query)"

    return dedent(
        f"""
        Optimise the following Freshservice help desk query so it returns the
        most relevant historical tickets. Retain the user's intent, surface key
        product names or technologies, and add related terminology if it helps
        catch similar issues. Keep the final output under 30 words and respond
        with a single line of plain text only.

        Original query: "{original}"
        """
    ).strip()


def create_guidance_system_message() -> str:
    """System directive for AI guidance generation."""

    return (
        "You are an experienced IT service desk agent. Using the current "
        "Freshservice ticket details alongside how similar historical tickets "
        "were handled (including work notes) and the category taxonomy, "
        "recommend actionable next steps for the assigned agent."
    )


def create_ai_guidance_prompt_with_sources(
    *,
    similar_tickets: Sequence[Dict[str, Any]],
    current_ticket: Dict[str, Any],
    detected_tokens: Sequence[str],
    category_taxonomy: Dict[str, Any],
    assignment_groups: Sequence[str],
) -> str:
    """Build the user prompt for AI guidance generation.

    The JSON payload mirrors what :func:`generate_guidance` expects back from the
    model: coaching text, a recommended category path, assignment group, and
    explicit supporting tickets. Keeping the schema centralised here helps the
    prompt and the response parser stay in lockstep.
    """

    payload = {
        "current_ticket": current_ticket,
        "similar_tickets": list(similar_tickets),
        "detected_tokens": _normalise_tokens(detected_tokens),
        "category_taxonomy": category_taxonomy,
        "assignment_groups": sorted({grp for grp in assignment_groups if grp}),
    }

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    guidance_instructions = dedent(
        """
        Using the JSON payload below--which pairs the ticket we are working on
        with knowledge of how similar tickets were handled--recommend next
        actions for the agent. Provide:
          • `agent_response_markdown`: succinct coaching written in markdown
          • `recommended_category_path`: array describing the best category path
          • `recommended_assignment_group`: name of the best-fit group (or null)
          • `confidence`: low/medium/high (or a short explanation)
          • `supporting_tickets`: list of objects with `ticket_id` and `rationale`

        Respond with valid JSON only. Reference the evidence from similar
        tickets when making recommendations and flag any gaps or risks.

        JSON payload:
        """
    ).strip()

    return f"{guidance_instructions}\n{payload_json}"


