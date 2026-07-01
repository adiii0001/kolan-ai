import json
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.tools.search_catalog import search_catalog, search_available, search_deals, search_new_products, search_best_sellers, search_deals_in_collection, get_all_products
from app.tools.get_policy import get_policy
from app.services.shopify_sync import get_all_collections, get_collection_products
from app.services.query_classifier import build_emotion_context, format_classification_for_prompt

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


client: Any = None
if settings.openai_api_key:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
    except Exception:
        logger.warning("Failed to initialize OpenAI client")
        client = None

SYSTEM_PROMPT = """You are Kolan AI, a friendly and knowledgeable shopping assistant for Kolan.
You help customers find products, answer questions about pricing, availability, features, shipping, refunds, returns, and policies.

BRAND KNOWLEDGE — Use this to answer questions about Kolan, why choose Kolan, ingredients, safety, etc:
Kolan makes plant-based, multi-enzymatic cleaning products and pet care products. Key facts:
- Products are MULTI-ENZYME based — they use natural enzymes (not chemicals) to break down dirt, grime, stains, and odours at a molecular level.
- 100% CHEMICAL-FREE — no harsh chemicals, no bleach, no ammonia, no phosphates, no parabens.
- PLANT-BASED ingredients — made from natural plant extracts and enzymes.
- BIODEGRADABLE — safe to wash down the drain, won't harm waterways or aquatic life.
- CRUELTY-FREE — never tested on animals.
- SAFE FOR BABIES, PETS, AND THE ENTIRE FAMILY — no toxic residues left on surfaces.
- ECO-FRIENDLY packaging and formulas — reduces environmental footprint.
- Multi-surface compatible — works on floors, bathrooms, kitchens, glass, toilets, laundry, leather, and more.
- No-rinse formulas available — just spray and wipe, no water needed after cleaning.
- Enzymes work by digesting organic matter — they break down bacteria, food stains, pet stains, odours, grease, and grime naturally.
- Kolan products are safe for septic tanks and do not pollute soil or waterways.
- The brand was founded on the mission to reconnect people with nature's cleaning wisdom — replacing toxic chemical cleaners with safe, natural alternatives.
- Products are made in India.
- Available in 700 mL bottles and combo packs (3-pack, 4-pack, 5-pack, 12-pack).

PRODUCT CATEGORIES:
- Household Cleaners: Floor Cleaner, Bathroom Cleaner, Kitchen Cleaner, Glass Cleaner, All Purpose Cleaner, Toilet Bowl Cleaner, Toilet Stain & Odour Killer
- Pet Care: Pet Stains & Odour Remover (for hard and soft surfaces), Pet Wipes (60 count packs)
- Laundry: Laundry Eco-Wash (enzyme-based detergent)
- Leather Care: Leather & Upholstery Cleaner
- Commercial: Farm & Stable Cleaner, Floor Cleaner (5L), Bathroom Cleaner (5L), etc.
- Combo Packs: Various multi-product bundles at discounted prices.

CRITICAL: You MUST use tools for EVERY product or collection question.

RULES:
- Use tools before answering. Use short keywords like "floor cleaner", "pet wipes", "bathroom cleaner".
- When customer asks about POLICIES (shipping, returns, refunds, privacy, terms), ALWAYS call get_policy — do NOT search products.
- When customer asks about a COLLECTION (e.g. "show me pet care", "what's in combo packs"), call get_collection with the handle.
- When customer asks about NEW PRODUCTS or WHAT'S NEW, call search_new_products.
- When customer asks about BEST SELLERS or MOST POPULAR, call search_best_sellers.
- When customer asks about DEALS, OFFERS, or DISCOUNTS, call search_deals.
- When referring to products, use short names like "floor cleaner", "pet wipes" — NOT the full product title.
- When customer asks about Kolan as a brand, WHY to buy, ingredients, safety, or eco-friendliness — use the BRAND KNOWLEDGE above to give specific, detailed answers.
- If a specific product is out of stock, say so politely and suggest in-stock alternatives.
- Never recommend out-of-stock items.
- CRITICAL: When showing products, keep your text VERY SHORT (1-2 sentences max). The product cards with images, prices, and links will be shown automatically. Do NOT list products in your text — just say something like "Here are some great options!" or "We have combo packs available!" and let the cards display.
- End responses with a friendly follow-up question to continue the conversation.
- Be warm, conversational, and helpful. Format as plain text, no markdown. Do NOT use asterisks, bold, italics, bullet points, numbered lists, or any special formatting. Use simple sentences with plain punctuation only."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search ALL products (in-stock and out-of-stock) by name, description, or tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Short search keywords like 'floor cleaner'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_available",
            "description": "Search ONLY in-stock products by name, description, or tags. Use for recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Short search keywords"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_deals",
            "description": "Find products currently on sale or with discounts. Use when customer asks about deals, offers, discounts, or sales.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_new_products",
            "description": "Show the newest and latest products. Use when customer asks about new arrivals, new products, or what's new.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_best_sellers",
            "description": "Show the most popular and top-selling products. Use when customer asks about best sellers, top products, or popular items.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_deals_in_collection",
            "description": "Find discounted products within a specific collection. Use when customer asks about deals in a collection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Collection handle like 'pet-wipes'"}
                },
                "required": ["handle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": "Get store policy. Valid types: shipping_policy, refund_policy, return_policy, privacy_policy, terms_of_service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_type": {"type": "string", "description": "Policy type to retrieve"}
                },
                "required": ["policy_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_collections",
            "description": "List all product collections.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_collection",
            "description": "Get products from a specific collection by handle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Collection handle"},
                    "limit": {"type": "integer", "description": "Max products to return"}
                },
                "required": ["handle"]
            }
        }
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "search_catalog":
        return search_catalog(args.get("query", ""))
    elif name == "search_available":
        return search_available(args.get("query", ""))
    elif name == "search_deals":
        return search_deals()
    elif name == "search_new_products":
        return search_new_products()
    elif name == "search_best_sellers":
        return search_best_sellers()
    elif name == "search_deals_in_collection":
        return search_deals_in_collection(args.get("handle", ""))
    elif name == "get_policy":
        return get_policy(args.get("policy_type", ""))
    elif name == "list_collections":
        return get_all_collections()
    elif name == "get_collection":
        return get_collection_products(args.get("handle", ""), args.get("limit", 20))
    return None


def collect_products_from_result(result, products):
    if not result:
        return
    for p in result:
        products.append({
            "title": p["title"],
            "price": p["price"],
            "image_url": p["image_url"],
            "handle": p["handle"],
            "available": p["available"],
            "first_variant_id": p.get("first_variant_id", ""),
            "short_description": p.get("short_description", ""),
            "compare_at_price": p.get("compare_at_price", 0),
        })


async def openai_chat(message: str, history: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if client is None:
        return {"answer": "AI service is not configured. Please set OPENAI_API_KEY.", "products": []}

    system = SYSTEM_PROMPT
    if context:
        ctx_block = format_context(context)
        if ctx_block:
            system = SYSTEM_PROMPT + "\n\n" + ctx_block

    class_info = build_emotion_context(message)
    system += format_classification_for_prompt(class_info)

    messages = [{"role": "system", "content": system}]
    for h in history:
        if h["role"] in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    products = []

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            temperature=0.1,
            max_tokens=1024,
        )

        choice = response.choices[0]
        answer = choice.message.content or ""

        if choice.message.tool_calls:
            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

                result = execute_tool(func_name, func_args)
                if func_name in ("search_catalog", "search_available", "get_collection", "search_deals", "search_new_products", "search_best_sellers", "search_deals_in_collection") and result:
                    collect_products_from_result(result, products)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False) if result else "No results found"
                })

            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            answer = final_response.choices[0].message.content or ""

    except Exception as e:
        logger.error("OpenAI chat error: %s", str(e), exc_info=True)
        return {"answer": "Sorry, I encountered an error. Please try again.", "products": []}

    mode = class_info["mode"]
    if not mode["show_images"] or not mode["recommend_products"]:
        products.clear()

    return {"answer": answer, "products": products}
