import json
import logging
from typing import List, Dict, Any, Optional

from anthropic import Anthropic

from app.core.config import settings
from app.tools.search_catalog import search_catalog, search_available, get_all_products
from app.tools.get_policy import get_policy

logger = logging.getLogger(__name__)


def format_context(ctx: Dict[str, Any]) -> str:
    parts = []
    page_type = ctx.get("pageType", "")
    if page_type:
        parts.append(f"Page: {page_type}")
    product = ctx.get("product")
    if product and product.get("title"):
        parts.append(f"Product: {product['title']} (Rs{product.get('price', '?')})")
    collection = ctx.get("collection")
    if collection and collection.get("title"):
        parts.append(f"Collection: {collection['title']}")
    cart = ctx.get("cart")
    if cart and cart.get("itemCount", 0) > 0:
        items = "; ".join(f"{i.get('title','?')} x{i.get('quantity',1)}" for i in (cart.get("items") or []))
        parts.append(f"Cart ({cart['itemCount']} items, Rs{cart.get('totalPrice','?')}): {items}")
    customer = ctx.get("customer")
    if customer and customer.get("firstName"):
        parts.append(f"Customer: {customer['firstName']}")
    banner = ctx.get("announcementBanner", "")
    if banner:
        parts.append(f"Announcement: {banner}")
    if not parts:
        return ""
    return "Current store context:\n" + "\n".join(parts)

client: Optional[Anthropic] = None
if settings.claude_api_key:
    client = Anthropic(api_key=settings.claude_api_key)

SYSTEM_PROMPT = """You are Kolan AI, a helpful shopping assistant for Kolan, a pet store.
You help customers find products, compare products, make personalized recommendations, and answer questions about pricing, availability, shipping, refunds, returns, and policies.

CRITICAL: You MUST use tools before answering any product question.

Tools:
1. search_catalog(query) - Search ALL products (in-stock and out-of-stock). Use short keywords.
2. search_available(query) - Search ONLY in-stock products. Use for recommendations and alternatives.
3. get_all_products() - Get every in-stock product (use for comparisons and personalized recommendations)
4. get_policy(policy_type) - Get store policy content

Rules:
- Use tools before answering. Use short keywords like "floor cleaner", "pet wipes".
- When referring to products, use short names like "floor cleaner" not the full title.
- If a specific product is out of stock, say: "This product is currently out of stock." Then use search_available to suggest in-stock alternatives.
- Never recommend out-of-stock items. Only recommend where available=true.
- If customer asks for a category (e.g. "bathroom cleaner"), use search_available to find in-stock options.
- If customer asks for "everything" or "all products", use get_all_products().
- Be friendly and concise. Include Rs prices. Format as plain text, no markdown."""

TOOLS = [
    {
        "name": "search_catalog",
        "description": "Search ALL products (in-stock and out-of-stock) by name, description, or tags. Each result has an 'available' field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find products"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_available",
        "description": "Search ONLY in-stock products by name, description, or tags. Use for recommendations and alternatives.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find available products"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_all_products",
        "description": "Get every in-stock product in the catalog. Use this for comparisons and personalized recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_policy",
        "description": "Get store policy information. Valid types: shipping_policy, refund_policy, return_policy, privacy_policy, terms_of_service",
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "The policy type to retrieve"
                }
            },
            "required": ["policy_type"]
        }
    }
]


def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "search_catalog":
        return search_catalog(args.get("query", ""))
    elif name == "search_available":
        return search_available(args.get("query", ""))
    elif name == "get_all_products":
        return get_all_products()
    elif name == "get_policy":
        return get_policy(args.get("policy_type", ""))
    return None


async def claude_chat(message: str, history: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if client is None:
        return {
            "answer": "AI service is not configured. Please set CLAUDE_API_KEY.",
            "products": []
        }

    system = SYSTEM_PROMPT
    if context:
        ctx_block = format_context(context)
        if ctx_block:
            system = SYSTEM_PROMPT + "\n\n" + ctx_block

    messages = []
    for h in history:
        if h["role"] in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=TOOLS,
        )

        products = []
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                func_name = content_block.name
                func_args = content_block.input if content_block.input else {}
                result = execute_tool(func_name, func_args)

                if func_name in ("search_catalog", "search_available", "get_all_products") and result:
                    for p in result:
                        products.append({
                            "title": p["title"],
                            "price": p["price"],
                            "image_url": p["image_url"],
                            "handle": p["handle"],
                            "available": p["available"],
                        })

                tool_results.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps(result) if result else "No results found"
                        }
                    ]
                })

        if tool_results:
            messages.append({"role": "assistant", "content": response.content})
            for tr in tool_results:
                messages.append(tr)

            final_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system,
                messages=messages,
            )
            answer = ""
            for block in final_response.content:
                if block.type == "text":
                    answer += block.text
        else:
            answer = ""
            for block in response.content:
                if block.type == "text":
                    answer += block.text

        return {"answer": answer or "I'm not sure how to help with that.", "products": products}

    except Exception as e:
        logger.error("Claude chat error: %s", str(e))
        return {"answer": "Sorry, I encountered an error. Please try again.", "products": []}
