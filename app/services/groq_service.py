import json
import logging
import re
from typing import List, Dict, Any, Optional

from groq import Groq

from app.core.config import settings
from app.tools.search_catalog import search_catalog, search_available
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

client: Optional[Groq] = None
if settings.groq_api_key:
    client = Groq(api_key=settings.groq_api_key, max_retries=0)

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

TOOLS (output exactly in this format to use a tool):
<function=search_catalog{"query": "short keywords here"}</function>
<function=search_available{"query": "short keywords here"}</function>
<function=get_policy{"policy_type": "shipping_policy"}</function>
<function=list_collections{}</function>
<function=get_collection{"handle": "collection-handle"}</function>

Available tools:
1. search_catalog(query) - Search ALL products (in-stock and out-of-stock).
2. search_available(query) - Search ONLY in-stock products. Use for recommendations.
3. get_policy(policy_type) - Get store policy. Valid types: shipping_policy, refund_policy, return_policy, privacy_policy, terms_of_service.
4. list_collections{} - List all product collections (pet-care, household-cleaners, commercial-cleaning, combo-packs, pet-wipes).
5. get_collection(handle, limit) - Get products from a specific collection. Use the collection handle.

COLLECTIONS AVAILABLE:
- pet-care: Pet care products
- household-cleaners: Household cleaning products
- commercial-cleaning: Commercial cleaning products
- combo-packs: Combo deals and bundles
- pet-wipes: Pet grooming wipes

RULES:
- Use tools before answering. Use short keywords like "floor cleaner", "pet wipes", "bathroom cleaner".
- When customer asks about POLICIES (shipping, returns, refunds, privacy, terms), ALWAYS call get_policy — do NOT search products.
- When customer asks about a COLLECTION (e.g. "show me pet care", "what's in combo packs", "commercial cleaning products"), call get_collection with the handle.
- When referring to products, use short names like "floor cleaner", "pet wipes" — NOT the full product title.
- When customer asks about Kolan as a brand, WHY to buy, ingredients, safety, or eco-friendliness — use the BRAND KNOWLEDGE above to give specific, detailed answers. Mention enzymes, plant-based, chemical-free, biodegradable, safe for babies/pets. Do NOT give generic answers.
- When customer asks about a SPECIFIC product, call search_catalog to find it, then describe its features based on the product description and brand knowledge (enzyme-based, chemical-free, safe for pets, etc).
- If a specific product is out of stock, say so politely and suggest in-stock alternatives.
- Never recommend out-of-stock items.
- CRITICAL: When showing products, keep your text VERY SHORT (1-2 sentences max). The product cards with images, prices, and links will be shown automatically. Do NOT list products in your text — just say something like "Here are some great options!" or "We have combo packs available!" and let the cards display.
- End responses with a friendly follow-up question to continue the conversation.
- Be warm, conversational, and helpful. Format as plain text, no markdown."""


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
    elif name == "list_collections":
        return get_all_collections()
    elif name == "get_collection":
        return get_collection_products(args.get("handle", ""), args.get("limit", 20))
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
            temperature=0.1,
            max_tokens=1024,
        )

        raw = response.choices[0].message.content or ""
        func_calls = parse_text_function_calls(raw)

        if func_calls:
            messages.append({"role": "assistant", "content": raw})
            tool_results = []
            for fc in func_calls:
                result = execute_tool(fc["name"], fc["arguments"])
                tool_results.append({"name": fc["name"], "result": result})
                if fc["name"] in ("search_catalog", "search_available", "get_collection") and result:
                    collect_products_from_result(result, products)
                messages.append({
                    "role": "user",
                    "content": json.dumps(result, ensure_ascii=False) if result else "No results found"
                })
            try:
                final_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                )
                answer = final_response.choices[0].message.content or ""
            except Exception:
                logger.warning("Groq follow-up call failed, using tool result directly")
                first_result = tool_results[0] if tool_results else None
                if first_result and first_result["name"] == "get_policy":
                    answer = first_result["result"]["content"]
                elif products:
                    in_stock = [p for p in products if p["available"]]
                    if in_stock:
                        summary = short_product_list_text(in_stock)
                        answer = f"I found these products:\n{summary}"
                    else:
                        answer = "Those products are currently out of stock."
                else:
                    answer = "I'm sorry, I couldn't find the information you're looking for."
        else:
            answer = raw

    except Exception as e:
        logger.error("Groq chat error: %s", str(e), exc_info=True)

        status = getattr(e, "status_code", None) or (getattr(e, "response", None) and getattr(e.response, "status_code", None))
        if status == 429:
            return {"answer": "I'm sorry, I'm a bit overwhelmed with requests right now. Please try again in a few minutes.", "products": []}

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
                first_call = func_calls[0]
                result = execute_tool(first_call["name"], first_call["arguments"])

                if first_call["name"] == "get_policy" and result:
                    answer = result["content"]
                    return {"answer": answer, "products": []}

                if first_call["name"] in ("search_catalog", "search_available", "get_collection") and result:
                    collect_products_from_result(result, products)

                    if not products:
                        answer = "I couldn't find any products matching your request. Please try a different search."
                        return {"answer": answer, "products": []}

                    in_stock = [p for p in products if p["available"]]
                    if not in_stock:
                        alt = search_available(extract_keywords(message))
                        if alt:
                            products.clear()
                            collect_products_from_result(alt, products)
                            in_stock = [p for p in products if p["available"]]

                    if in_stock:
                        summary = short_product_list_text(in_stock)
                        answer = f"I found some products that might interest you:\n{summary}\n\nWould you like more details on any of these?"
                    else:
                        answer = "Those products are currently out of stock. Try searching for something else!"
                    return {"answer": answer, "products": products}

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
                {"role": "system", "content": "You are a friendly pet store assistant. Keep your response to 1-2 sentences MAX. Product cards with images and prices will be shown automatically below your text — do NOT list products or prices in your reply. Just mention key features (eco-friendly, multi-pack, natural). End with a follow-up question. No markdown."},
                {"role": "user", "content": f"Customer asked: {message}\nIn-stock:\n{summary}{oos_note}\n\nCraft a very short response (1-2 sentences). Do NOT list products."}
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
                        {"role": "system", "content": "You are a friendly pet store assistant. Keep your response to 1-2 sentences MAX. Product cards with images and prices will be shown automatically below your text — do NOT list products or prices. Just say items are out of stock and cards show alternatives. No markdown."},
                        {"role": "user", "content": f"Customer asked: {message}\nRequested items are out of stock. In-stock alternatives:\n{summary}\n\nCraft a very short response (1-2 sentences). Do NOT list products."}
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
