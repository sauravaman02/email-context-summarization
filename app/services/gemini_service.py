"""Gemini API client for email summarisation.

Handles prompt construction, API calls with retry/exponential-backoff,
response parsing and validation, and token usage tracking. The prompt
instructs Gemini to return structured JSON with three keys: actors,
concluded_discussions, and open_action_items.
"""

import asyncio
import json
import logging
import random

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = """You are an expert email analyst for a CPA (Certified Public Accountant) firm.
Analyze the following email thread between firm accountants and a client.

Extract structured intelligence and return a JSON object with exactly these three keys:

1. "actors" — every person mentioned or involved:
   Each entry: {{"name": "<full name>", "role": "<e.g. Accountant, Client, IRS Agent>", "involvement": "<one-sentence description>"}}

2. "concluded_discussions" — topics that have been resolved:
   Each entry: {{"topic": "<topic>", "resolution": "<how it was resolved>", "resolved_date": "<YYYY-MM-DD or unknown>"}}

3. "open_action_items" — pending tasks or unresolved matters:
   Each entry: {{"item": "<description>", "assigned_to": "<person name>", "priority": "<high|medium|low>", "context": "<why it matters>"}}

Rules:
- Be thorough but concise.
- Identify ALL actors, even those only mentioned in passing.
- Distinguish clearly between resolved and pending items.
- Assign priority based on urgency indicators (deadlines, regulatory requirements, client frustration).

Email Thread:
---
{emails}
---

Respond ONLY with valid JSON. No markdown fences, no explanation, no preamble."""


def _format_emails(emails: list[dict]) -> str:
    """Format a list of email dicts into a human-readable thread for the prompt."""
    parts: list[str] = []
    for i, e in enumerate(emails, 1):
        recipients = ", ".join(
            r.get("name", r.get("email", "Unknown")) for r in e.get("recipients", [])
        )
        parts.append(
            f"Email #{i}\n"
            f"From: {e['sender_name']} <{e['sender_email']}>\n"
            f"To: {recipients}\n"
            f"Date: {e['sent_at']}\n"
            f"Subject: {e.get('subject', '(no subject)')}\n"
            f"Body:\n{e['body']}\n"
        )
    return "\n---\n".join(parts)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if Gemini wraps the JSON response."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def _extract_token_usage(response) -> tuple[int, int]:
    """Safely extract input/output token counts from Gemini's response metadata."""
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    return input_tokens, output_tokens


async def summarize_emails(
    emails: list[dict],
) -> tuple[dict, int, int]:
    """Call Gemini to summarize an email thread.

    Implements retry with exponential backoff and jitter. Validates that the
    response contains all required keys before returning.

    Returns:
        (summary_dict, input_tokens, output_tokens)

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    client = genai.Client(api_key=settings.gemini_api_key)

    formatted = _format_emails(emails)
    prompt = SUMMARIZATION_PROMPT.format(emails=formatted)

    max_retries = settings.summarization_max_retries
    base_delay = settings.summarization_retry_base_delay
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )

            input_tokens, output_tokens = _extract_token_usage(response)

            text = _strip_markdown_fences(response.text.strip())
            summary = json.loads(text)

            required_keys = {"actors", "concluded_discussions", "open_action_items"}
            if not required_keys.issubset(summary.keys()):
                missing = required_keys - set(summary.keys())
                logger.warning("Gemini response missing keys: %s — retrying", missing)
                raise ValueError(f"Missing keys in response: {missing}")

            logger.info(
                "Gemini summarization succeeded (attempt %d, in=%d, out=%d tokens)",
                attempt + 1,
                input_tokens,
                output_tokens,
            )
            return summary, input_tokens, output_tokens

        except Exception as exc:
            last_exception = exc
            if attempt < max_retries - 1:
                jitter = random.uniform(0, 0.5)
                wait = base_delay * (2**attempt) + jitter
                logger.warning(
                    "Gemini API attempt %d/%d failed (%s) — retrying in %.1fs",
                    attempt + 1,
                    max_retries,
                    str(exc)[:120],
                    wait,
                )
                await asyncio.sleep(wait)

    logger.error("Gemini API failed after %d attempts: %s", max_retries, last_exception)
    raise RuntimeError(f"Gemini API failed after {max_retries} retries") from last_exception
