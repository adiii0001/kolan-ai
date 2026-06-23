import re
from typing import Dict, Any, List

POLICY_KEYWORDS = {
    "shipping_policy": ["shipping", "ship", "delivery", "dispatch", "courier", "shipped"],
    "return_policy": ["return", "returns", "returning", "exchange", "replacement"],
    "refund_policy": ["refund", "refunds", "money back", "cancel order", "cancellation"],
    "privacy_policy": ["privacy", "personal information", "data", "gdpr", "private"],
    "terms_of_service": ["terms", "terms of service", "t&c", "terms and conditions", "conditions"],
    "warranty_policy": ["warranty", "guarantee", "guaranteed", "coverage"],
}

RECOMMEND_KEYWORDS = [
    "recommend", "suggest", "suggestion", "best", "top", "favorite", "popular",
    "which one", "which product", "what should", "what do you think",
    "ideal for", "perfect for", "good for", "适合", "推荐",
]

COMPARISON_KEYWORDS = [
    "compare", "comparison", "versus", "vs", "difference between",
    "better than", "which is better",
]

EMOTION_PATTERNS: Dict[str, List[str]] = {
    "frustrated": [
        r"\b(annoying?|frustrat(ed|ing)|angry|mad|upset|not happy|disappoint(ed|ing)|terrible|worst|horrible|useless)\b",
        r"\b(waste of|doesn't work|not working|broken|fed up|sick of)\b",
    ],
    "urgent": [
        r"\b(urgent(ly)?|asap|immediately?|quick(ly)?|hurry|running out|emergency|important|need it now)\b",
        r"\b(tomorrow|today asap|right now|right away|soon|fast|delayed?|running late)\b",
    ],
    "confused": [
        r"\b(confus(ed|ing)?|don't understand|not sure|unclear|what does|how do(es)?|help me understand)\b",
        r"\b(what is|what are|explain|mean|complicated|does this|how this)\b",
    ],
    "happy": [
        r"\b(great|awesome|amazing|love|perfect|wonderful|excellent|fantastic|happy|satisfied|best ever)\b",
        r"\b(thank|thanks|appreciate|pleased|works great|delighted)\b",
    ],
    "dissatisfied": [
        r"\b(bad|poor|cheap|low quality|damaged|defective|wrong item|missing|not as described)\b",
        r"\b(complaint|issue|problem|mistake|error|dissatisfied|unhappy)\b",
    ],
}


def classify_query(message: str) -> str:
    msg_lower = message.lower().strip()

    for policy_type, keywords in POLICY_KEYWORDS.items():
        for kw in keywords:
            if kw in msg_lower:
                return "policy"

    for pattern in EMOTION_PATTERNS["dissatisfied"]:
        if re.search(pattern, msg_lower):
            return "complaint"
    for pattern in EMOTION_PATTERNS["frustrated"]:
        if re.search(pattern, msg_lower):
            return "complaint"

    for kw in RECOMMEND_KEYWORDS:
        if kw in msg_lower:
            return "recommendation"

    for kw in COMPARISON_KEYWORDS:
        if kw in msg_lower:
            return "comparison"

    support_patterns = [
        r"\b(order|ordered|order id|tracking|delivery|dispatch)\b.*\b(issue|problem|delayed|missing|wrong|not received|not arrived)\b",
        r"\b(where is|status of|track|update on)\b.*\b(order|delivery|shipment)\b",
        r"\b(cancel|change|modify)\b.*\b(order)\b",
    ]
    for pattern in support_patterns:
        if re.search(pattern, msg_lower):
            return "support"

    product_search_intent = [
        r"\b(show|find|looking for|want|have|get|buy|purchase|see)\b",
        r"\b(available|in stock|price|cost|how much)\b",
        r"\b(product|item|option|variant)\b",
    ]
    for pattern in product_search_intent:
        if re.search(pattern, msg_lower):
            return "product_search"

    product_info_patterns = [
        r"\b(what is|tell me about|details|ingredients|sizes?|features?)\b",
        r"\bhow\b.*\b(product|item|food|treat|cleaner|wipe|shampoo|toy|bed|carrier|bowl|leash|collar|harness)\b",
    ]
    for pattern in product_info_patterns:
        if re.search(pattern, msg_lower):
            return "product_info"

    return "general"


def detect_emotions(message: str) -> Dict[str, float]:
    msg_lower = message.lower()
    emotions: Dict[str, float] = {
        "positive": 0.0,
        "negative": 0.0,
        "urgent": 0.0,
        "confused": 0.0,
        "frustrated": 0.0,
        "neutral": 0.8,
    }

    for emotion, patterns in EMOTION_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            found = re.findall(pattern, msg_lower)
            matches += len(found)
        if matches > 0:
            confidence = min(0.3 + (matches * 0.15), 0.95)
            emotions[emotion] = confidence
            emotions["neutral"] = max(0.0, emotions["neutral"] - confidence * 0.5)

    positive_words = ["love", "great", "amazing", "perfect", "awesome", "happy", "wonderful", "excellent", "fantastic", "good", "nice", "best ever", "thank", "thanks", "appreciate", "delighted", "satisfied"]
    negative_words = ["bad", "worst", "terrible", "horrible", "awful", "poor", "hate", "disappointed", "frustrated", "angry", "ugly", "broken", "damaged", "defective", "useless", "waste"]

    pos_count = sum(1 for w in positive_words if w in msg_lower)
    neg_count = sum(1 for w in negative_words if w in msg_lower)

    if pos_count > neg_count:
        emotions["positive"] = max(emotions["positive"], min(0.3 + pos_count * 0.15, 0.95))
        emotions["negative"] = 0.0
        emotions["neutral"] = 0.2
    elif neg_count > pos_count:
        emotions["negative"] = max(emotions["negative"], min(0.3 + neg_count * 0.15, 0.95))
        emotions["positive"] = 0.0
        emotions["neutral"] = 0.1

    return {k: v for k, v in emotions.items() if v > 0.15}


def get_emotion_label(emotions: Dict[str, float]) -> str:
    if not emotions:
        return "neutral"
    return max(emotions, key=emotions.get)


def get_response_mode(query_type: str, emotions: Dict[str, float]) -> Dict[str, Any]:
    emotion_label = get_emotion_label(emotions)
    primary_emotion_score = emotions.get(emotion_label, 0.0)

    mode: Dict[str, Any] = {
        "show_images": True,
        "recommend_products": True,
        "search_products": True,
        "tone": "friendly",
        "empathetic": False,
        "escalate": False,
        "apologetic": False,
    }

    if query_type == "policy":
        mode["show_images"] = False
        mode["recommend_products"] = False
        mode["search_products"] = False
        mode["tone"] = "informative"

    elif query_type == "complaint":
        mode["show_images"] = False
        mode["recommend_products"] = False
        mode["search_products"] = False
        mode["tone"] = "empathetic"
        mode["empathetic"] = True

    elif query_type == "general":
        mode["show_images"] = False
        mode["recommend_products"] = False
        mode["tone"] = "friendly"

    elif query_type == "support":
        mode["recommend_products"] = False
        mode["tone"] = "helpful"

    if emotion_label == "frustrated" and primary_emotion_score > 0.4:
        mode["tone"] = "apologetic"
        mode["empathetic"] = True
        mode["recommend_products"] = False
        mode["apologetic"] = True
    elif emotion_label == "urgent":
        mode["tone"] = "efficient"
        mode["empathetic"] = True
    elif emotion_label == "confused":
        mode["tone"] = "clarifying"
        mode["empathetic"] = True
    elif emotion_label == "happy" or emotion_label == "positive":
        if query_type not in ("policy", "complaint"):
            mode["tone"] = "enthusiastic"
    elif emotion_label == "negative" or emotion_label == "dissatisfied":
        mode["tone"] = "empathetic"
        mode["empathetic"] = True
        mode["recommend_products"] = False

    return mode


def build_emotion_context(message: str) -> Dict[str, Any]:
    query_type = classify_query(message)
    emotions = detect_emotions(message)
    mode = get_response_mode(query_type, emotions)
    emotion_label = get_emotion_label(emotions)

    return {
        "query_type": query_type,
        "emotions": emotions,
        "emotion_label": emotion_label,
        "mode": mode,
    }


def format_classification_for_prompt(class_info: Dict[str, Any]) -> str:
    mode = class_info["mode"]
    lines = [
        f"\n[QUERY CLASSIFICATION: {class_info['query_type'].upper()}]",
        f"[USER EMOTION: {class_info['emotion_label'].upper()}]",
        f"[TONE: {mode['tone'].upper()}]",
    ]

    if not mode["show_images"]:
        lines.append("[INSTRUCTION: Do NOT show or mention product images. Focus on information only.]")
    if not mode["recommend_products"]:
        lines.append("[INSTRUCTION: Do NOT recommend or suggest products. Only answer the question directly.]")
    if not mode["search_products"]:
        lines.append("[INSTRUCTION: Do NOT search for products. Only use informational tools like get_policy.]")
    if mode["empathetic"]:
        lines.append("[INSTRUCTION: Respond with empathy. Acknowledge the user's feelings before providing information.]")
    if mode["apologetic"]:
        lines.append("[INSTRUCTION: Apologize sincerely for their experience and offer to help resolve the issue.]")
    if class_info["query_type"] == "policy":
        lines.append("[INSTRUCTION: Policy question. Use get_policy tool and answer factually. Do NOT search for or suggest products.]")
    if class_info["emotion_label"] == "confused":
        lines.append("[INSTRUCTION: The user seems confused. Explain clearly and simply. Offer to clarify further.]")
    if class_info["emotion_label"] == "urgent":
        lines.append("[INSTRUCTION: The user seems urgent. Be direct and efficient. Prioritize getting them the answer quickly.]")

    return "\n".join(lines)
