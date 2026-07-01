import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.services.groq_service import groq_chat
from app.services.claude_service import claude_chat
from app.services.openai_service import openai_chat
from app.services.query_classifier import build_emotion_context

logger = logging.getLogger(__name__)

USE_OPENAI = True  # Set False to fall back to Groq


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
    class_info = build_emotion_context(message)
    emotion_label = class_info["emotion_label"]
    query_type = class_info["query_type"]

    has_openai = bool(settings.openai_api_key)
    has_claude = bool(settings.claude_api_key)
    has_groq = bool(settings.groq_api_key)

    use_claude = needs_claude(message) and has_claude

    if not use_claude and has_claude:
        if query_type in ("complaint",) and emotion_label in ("frustrated", "dissatisfied"):
            logger.info("Routing complaint/emotional message to Claude")
            use_claude = True
        elif query_type == "comparison":
            logger.info("Routing comparison to Claude")
            use_claude = True

    if use_claude:
        logger.info("Routing to Claude (query=%s, emotion=%s)", query_type, emotion_label)
        return await claude_chat(message, history, context=context)

    if USE_OPENAI and has_openai:
        logger.info("Routing to OpenAI GPT-4o-mini (query=%s, emotion=%s)", query_type, emotion_label)
        return await openai_chat(message, history, context=context)

    if has_groq:
        logger.info("Routing to Groq (query=%s, emotion=%s)", query_type, emotion_label)
        return await groq_chat(message, history, context=context)

    return {"answer": "No AI service is configured. Please set OPENAI_API_KEY, GROQ_API_KEY, or CLAUDE_API_KEY.", "products": []}
