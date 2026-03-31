import contextvars
import logging
from decimal import Decimal
from typing import Any
from app.db import database
from app.db.models import LLMUsageEvent

logger = logging.getLogger(__name__)

# Context variables to track the current request context
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar('llm_session_id', default="unknown")
_endpoint: contextvars.ContextVar[str] = contextvars.ContextVar('llm_endpoint', default="unknown")

def set_tracking_context(session_id: str, endpoint: str):
    """Sets the context for the current request."""
    _session_id.set(session_id)
    _endpoint.set(endpoint)

def clear_tracking_context():
    """Clears the context."""
    _session_id.set("unknown")
    _endpoint.set("unknown")

# Cost calculations (Gemini 2.5 Flash Pricing)
PRICE_PER_1M_PROMPT = Decimal("0.075")
PRICE_PER_1M_COMPLETION = Decimal("0.30")

async def track_gemini_usage(response: Any) -> None:
    """
    Extracts token usage from a Gemini response and saves it to the database.
    Does not block execution (fail-open).
    """
    try:
        if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            logger.warning("No usage_metadata found in Gemini response.")
            return

        usage = response.usage_metadata
        prompt_tokens = getattr(usage, 'prompt_token_count', 0) or 0
        completion_tokens = getattr(usage, 'candidates_token_count', 0) or 0
        total_tokens = getattr(usage, 'total_token_count', 0) or 0

        input_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * PRICE_PER_1M_PROMPT
        output_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * PRICE_PER_1M_COMPLETION
        total_cost = input_cost + output_cost

        session_id = _session_id.get()
        endpoint = _endpoint.get()

        if database.AsyncSessionLocal:
            async with database.AsyncSessionLocal() as db_session:
                event = LLMUsageEvent(
                    session_id=session_id,
                    endpoint=endpoint,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    input_cost_usd=input_cost,
                    output_cost_usd=output_cost,
                    total_cost_usd=total_cost
                )
                db_session.add(event)
                await db_session.commit()
                
        logger.info(f"LLM Tracked: {total_tokens} tokens for ${total_cost:.5f} (Session: {session_id})")

    except Exception as e:
        logger.error(f"Failed to track LLM usage: {e}")
