"""Aircraft narrative generation via Anthropic Claude API, enriched with civil register data."""

import logging

from anthropic import Anthropic

from .registers import lookup as lookup_register
from .registers.base import RegisterData

log = logging.getLogger(__name__)


def generate_aircraft_narrative(
    registration: str,
    aircraft_type: str | None,
    api_key: str,
    **register_kwargs,
) -> tuple[str | None, dict | None]:
    """Generate a concise narrative about an aircraft's history.

    Looks up the registration on the relevant country register (if supported)
    and provides that data to Claude as context.

    Returns (narrative_text, register_cache_dict) — either may be None.
    """
    if not api_key:
        return None, None

    # Try register lookup
    register_data = lookup_register(registration, **register_kwargs)

    if register_data:
        context = register_data.to_prompt_context()
        has_history = bool(register_data.ownership_timeline)
        history_instruction = (
            "its ownership journey through the years, "
            if has_history
            else ""
        )
        military_instruction = (
            "If there's a military serial, mention its military service. "
            if register_data.military_serial
            else ""
        )
        prompt = (
            f"Based on the following official register data for aircraft {registration}, "
            f"write a concise 2–3 paragraph narrative about this aircraft's history. "
            f"Cover its manufacturing, the type's background, {history_instruction}"
            f"and current status. {military_instruction}"
            f"Weave the register facts into engaging prose — don't just list the data.\n\n"
            f"{context}"
        )
    else:
        type_context = f" It is a {aircraft_type}." if aircraft_type else ""
        prompt = (
            f"Write a concise 2–3 paragraph narrative about the aircraft with "
            f"registration {registration}.{type_context} Cover its manufacturing "
            f"and delivery history, operators over the years, any notable events, "
            f"and current status if known. Be factual and concise. If you don't "
            f"have specific information about this registration, say so honestly "
            f"rather than fabricating details."
        )

    cache_dict = register_data.to_cache_dict() if register_data else None

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text, cache_dict
    except Exception:
        log.exception("Failed to generate narrative for %s", registration)
        return None, cache_dict
