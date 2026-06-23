import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.services.groq_service import groq_chat
from app.services.claude_service import claude_chat

logger = logging.getLogger(__name__)


def needs_claude(message: str) -> bool:
    triggers = [
        "compare", "comparison", "versus", "vs", "difference between",
        "recommend", "suggestion", "suggest", "best for",
        "which one", "which product", "what should",
        "allergies", "sensitive", "skin condition",
        "my dog", "my cat", "my pet",
        "personalized", "更适合", "推荐",
    ]
    msg_lower = message.lower()

    for trigger in triggers:
        if trigger in msg_lower:
            logger.info("Claude trigger matched: '%s'", trigger)
            return True

    if len(message.split()) > 30:
        logger.info("Long message, routing to Claude")
        return True

    return False


async def route_chat(message: str, history: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    use_claude = needs_claude(message) and bool(settings.claude_api_key)
    logger.info("Routing message to %s", "Claude" if use_claude else "Groq")

    if use_claude:
        return await claude_chat(message, history, context=context)
    else:
        return await groq_chat(message, history, context=context)
