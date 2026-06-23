import json
import logging
import re
from typing import List, Dict, Any, Optional

from groq import Groq

from app.core.config import settings
from app.tools.search_catalog import search_catalog, search_available
from app.tools.get_policy import get_policy
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

client: Optional[Groq] = None
if settings.groq_api_key:
    client = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are Kolan AI, a friendly and knowledgeable shopping assistant for Kolan, a pet store.
You help customers find products, answer questions about pricing, availability, features, shipping, refunds, returns, and policies.

CRITICAL: You MUST use search_catalog or search_available for EVERY product question.

TOOLS:
1. search_catalog(query) - Search ALL products (in-stock and out-of-stock). Returns 'available' field.
2. search_available(query) - Search ONLY in-stock products. Use for recommendations.
3. get_policy(type) - Get store policy. Use this for ANY policy question (shipping, returns, refunds, privacy, terms).

RULES:
- Use tools before answering. Use short keywords like "floor cleaner", "pet wipes", "bathroom cleaner".
- When customer asks about POLICIES (shipping, returns, refunds, privacy, terms), ALWAYS call get_policy — do NOT search products.
- When referring to products, use short names like "floor cleaner", "pet wipes" — NOT the full product title.
- Focus on product FEATURES: eco-friendly, gentle on pets, natural ingredients, sizes, quantities available.
- If a specific product is out of stock, say so politely and suggest in-stock alternatives.
- Never recommend out-of-stock items.
- End responses with a friendly follow-up question to continue the conversation (e.g. "Which variant would suit your needs?", "Would you like to know more about any of these?", "What kind of pet do you have?").
- Be warm, conversational, and helpful. Format as plain text, no markdown."""

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search ALL products (in-stock and out-of-stock). Returns available=true/false. Use short keywords like 'floor cleaner'. If the customer wants to see everything or browse, search with an empty string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Short keywords like 'floor cleaner' or '' for all products"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_available",
            "description": "Search ONLY in-stock products. Best for recommendations, alternatives, and category browsing. Use short keywords like 'pet wipes'. Use '' to show everything in stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Short keywords like 'floor cleaner' or '' for all in-stock products"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
        "name": "get_policy",
        "description": "Get store policy content. Types: shipping_policy, refund_policy, return_policy, privacy_policy, terms_of_service. Use this for ANY policy or terms questions — do NOT search for products when customer asks about policies.",
        "parameters": {
                "type": "object",
                "properties": {
                    "policy_type": {
                        "type": "string"
                    }
                },
                "required": ["policy_type"]
            }
        }
    }
]


# Match Groq's text-based function calls like:
# <function=search_catalog {"query": "pet wipes"}</function>
# or with extra >: <function=search_catalog {"query": "pet wipes"}></function>
FUNC_RE = re.compile(r'<function=(\w+)\s*(\{.*?\})')


def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "search_catalog":
        return search_catalog(args.get("query", ""))
    elif name == "search_available":
        return search_available(args.get("query", ""))
    elif name == "get_policy":
        return get_policy(args.get("policy_type", ""))
    return None


def parse_text_function_calls(text: str) -> List[Dict[str, Any]]:
    calls = []
    for match in FUNC_RE.finditer(text):
        try:
            calls.append({
                "name": match.group(1),
                "arguments": json.loads(match.group(2))
            })
        except json.JSONDecodeError:
            continue
    return calls


def extract_keywords(text: str) -> str:
    stopwords = {
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
        "what", "which", "who", "whom", "when", "where", "why", "how",
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "need", "like", "love",
        "tell", "show", "find", "look", "search", "give", "get", "want",
        "about", "for", "with", "without", "and", "or", "but", "in", "on",
        "at", "to", "from", "by", "of", "any", "some", "all", "please",
        "thanks", "thank", "hello", "hi", "hey", "there",
        "do", "does", "did", "have", "has", "had", "got",
        "available", "stock", "price", "cost", "recommend", "suggest",
        "products", "product", "items", "item", "options", "option",
        "policy", "policies", "return", "returns", "shipping", "refund",
        "refunds", "privacy", "terms", "warranty",
    }
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in cleaned.split() if w not in stopwords and len(w) > 1]
    return " ".join(words[:5]) if words else text


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
        })


def product_list_text(products):
    return "\n".join(f"- {p['title']} -- Rs{p['price']}" for p in products)


def short_product_list_text(products, max_items=6):
    lines = []
    for p in products[:max_items]:
        short_name = p["title"].replace("Kolan ", "").replace("Organic ", "").replace("Enzyme Based ", "").replace("Biodegradable, ", "").strip()
        if len(short_name) > 50:
            short_name = short_name[:50] + "..."
        lines.append(f"- {short_name} -- Rs{p['price']}")
    total = len(products)
    if total > max_items:
        lines.append(f"... and {total - max_items} more")
    return "\n".join(lines)


async def groq_chat(message: str, history: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if client is None:
        return {"answer": "AI service is not configured. Please set GROQ_API_KEY.", "products": []}

    system = SYSTEM_PROMPT
    if context:
        ctx_block = format_context(context)
        if ctx_block:
            system = SYSTEM_PROMPT + "\n\n" + ctx_block

    class_info = build_emotion_context(message)
    system += format_classification_for_prompt(class_info)

    messages = [{"role": "system", "content": system}]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": message})

    answer = ""
    products = []

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOLS_DEFINITION,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1024,
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            msg = choice.message.model_dump(exclude_unset=True)
            msg["role"] = "assistant"
            messages.append(msg)

            for tc in choice.message.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments)
                result = execute_tool(func_name, func_args)

                if func_name in ("search_catalog", "search_available") and result:
                    collect_products_from_result(result, products)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False) if result else "No results found"
                })

            final_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            answer = final_response.choices[0].message.content or ""

        else:
            raw = choice.message.content or ""
            func_calls = parse_text_function_calls(raw) if raw else []

            if func_calls:
                messages.append({"role": "assistant", "content": raw})
                for fc in func_calls:
                    result = execute_tool(fc["name"], fc["arguments"])
                    if fc["name"] in ("search_catalog", "search_available") and result:
                        collect_products_from_result(result, products)
                    messages.append({
                        "role": "user",
                        "content": f"Tool result: {json.dumps(result, ensure_ascii=False) if result else 'No results found'}"
                    })
                final_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                )
                answer = final_response.choices[0].message.content or ""
            else:
                answer = raw

    except Exception as e:
        logger.error("Groq chat error: %s", str(e), exc_info=True)
        failed_gen = ""
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    failed_gen = resp.json().get("error", {}).get("failed_generation", "") or ""
                except Exception:
                    failed_gen = ""
            if not failed_gen:
                body = getattr(e, "body", None)
                if isinstance(body, dict):
                    failed_gen = body.get("error", {}).get("failed_generation", "") or ""
        except Exception:
            pass

        if failed_gen:
            func_calls = parse_text_function_calls(failed_gen)
            if func_calls:
                for fc in func_calls:
                    result = execute_tool(fc["name"], fc["arguments"])
                    if fc["name"] in ("search_catalog", "search_available") and result:
                        collect_products_from_result(result, products)

                if func_calls[0]["name"] in ("search_catalog", "search_available") and products and client:
                    summary = short_product_list_text(products)
                    follow = [
                        {"role": "system", "content": "You are a friendly pet store assistant. Highlight product FEATURES like eco-friendly, gentle, sizes. Use short names. End with a follow-up question. No markdown."},
                        {"role": "user", "content": f"Customer asked about products. I found:\n{summary}\n\nCraft a friendly response highlighting features and ask a follow-up."}
                    ]
                    try:
                        follow_resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=follow,
                            temperature=0.5,
                            max_tokens=500,
                        )
                        answer = follow_resp.choices[0].message.content or ""
                        if answer:
                            return {"answer": answer, "products": products}
                    except Exception:
                        pass
                return {"answer": "Here are some products I found:", "products": products}

    # Fallback: if no products and answer is empty or generic "sorry", extract keywords and auto-search
    policy_keywords = ["policy", "return", "shipping", "refund", "privacy", "terms", "warranty"]
    is_policy_question = any(w in message.lower() for w in policy_keywords)
    sorry_patterns = ["couldn't find", "not found", "no products", "no results", "didn't find", "can't find", "unable to find"]
    skip_search = not class_info["mode"]["search_products"]
    needs_search = not products and not is_policy_question and not skip_search and (not answer or any(p in answer.lower() for p in sorry_patterns))

    if needs_search:
        keywords = extract_keywords(message)
        if keywords:
            result = search_catalog(keywords)
            if result:
                collect_products_from_result(result, products)

        if not products:
            result = search_catalog("")
            if result:
                collect_products_from_result(result, products)

    if products:
        in_stock = [p for p in products if p["available"]]
        out_of_stock = [p for p in products if not p["available"]]

        if in_stock:
            summary = short_product_list_text(in_stock)
            oos_note = ""
            if out_of_stock:
                oos_note = f"\n{len(out_of_stock)} other similar products are currently out of stock."
            follow = [
                {"role": "system", "content": "You are a friendly pet store assistant. Highlight features like eco-friendly, gentle, multi-pack options, natural ingredients. Use short names. End with a follow-up question. No markdown."},
                {"role": "user", "content": f"Customer asked: {message}\nIn-stock:\n{summary}{oos_note}\n\nCraft a warm response highlighting features and ask a follow-up question."}
            ]
            try:
                follow_resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=follow,
                    temperature=0.5,
                    max_tokens=500,
                )
                answer = follow_resp.choices[0].message.content or ""
            except Exception:
                short_names = [p["title"].replace("Kolan ", "").replace("Organic ", "").strip() for p in in_stock]
                answer = f"I found {len(in_stock)} in-stock products:\n" + "\n".join(f"- {n} - Rs{p['price']}" for n, p in zip(short_names, in_stock))

        elif out_of_stock:
            alt_result = search_available(extract_keywords(message))
            if alt_result:
                collect_products_from_result(alt_result, products)
                in_stock = [p for p in alt_result if p["available"]]
                if in_stock:
                    summary = short_product_list_text(in_stock)
                    follow = [
                        {"role": "system", "content": "You are a friendly pet store assistant. Politely inform the customer their requested items are out of stock. Highlight features of alternatives. End with a helpful follow-up question. No markdown."},
                        {"role": "user", "content": f"Customer asked: {message}\nRequested items are out of stock. In-stock alternatives:\n{summary}\n\nCraft a friendly response saying they're out of stock, highlight alternative features, and ask a follow-up."}
                    ]
                    try:
                        follow_resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=follow,
                            temperature=0.5,
                            max_tokens=500,
                        )
                        answer = follow_resp.choices[0].message.content or ""
                    except Exception:
                        pass

            if not answer:
                answer = "The products you're looking for are currently out of stock. Try searching for something else or check back later!"

    if not answer:
        if is_policy_question:
            policy_type = None
            for kw in policy_keywords:
                if kw in message.lower():
                    if kw == "return" or kw == "returns":
                        policy_type = "return_policy"
                    elif kw == "shipping":
                        policy_type = "shipping_policy"
                    elif kw == "refund" or kw == "refunds":
                        policy_type = "refund_policy"
                    elif kw == "privacy":
                        policy_type = "privacy_policy"
                    elif kw == "terms":
                        policy_type = "terms_of_service"
                    elif kw == "warranty":
                        policy_type = "warranty_policy"
                    break
            if policy_type:
                from app.tools.get_policy import get_policy
                pol = get_policy(policy_type)
                if pol:
                    answer = pol["content"]
                else:
                    answer = "I don't have that policy information right now. Please contact our support team for assistance."
        else:
            answer = "Sorry, I couldn't find any products matching your request. Please try a different search."

    mode = class_info["mode"]
    if not mode["show_images"] or not mode["recommend_products"]:
        products.clear()

    return {"answer": answer, "products": products}
