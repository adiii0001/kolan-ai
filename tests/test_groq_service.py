import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path("C:/Users/Aditya Verma/OneDrive/Desktop/AIKolan project/kolan-ai")))
os.environ["DATABASE_URL"] = str(pathlib.Path(__file__).parent / "test_kolan_groq.db")

import pytest
from app.core.database import init_db, get_connection
from app.services.groq_service import groq_chat, execute_tool, extract_keywords, parse_price_limit, collect_products_from_result


@pytest.fixture(autouse=True)
def setup_db():
    db_path = pathlib.Path(__file__).parent / "test_kolan_groq.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    products = [
        ("pw1", "Kolan Pet Wipes 60 Count", "pet-wipes", 330.0, 395.0, 1),
        ("pw2", "Kolan Pet Wipes Pack of 2",
         "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-2",
         599.0, 790.0, 1),
        ("cl1", "Kolan Floor Cleaner", "no-rinse-floor-cleaner", 489.0, 495.0, 1),
        ("cl2", "Kolan Bathroom Cleaner", "bathroom-cleaner", 389.0, 395.0, 1),
    ]
    for s_id, title, handle, price, comp, avail in products:
        cursor.execute("""
            INSERT INTO products (shopify_id, title, handle, description, price,
                compare_at_price, first_variant_id, vendor, product_type, tags,
                image_url, inventory_quantity, available, shopify_created_at)
            VALUES (?,?,?,'desc',?,?,'v1','Kolan','cleaner','','img.jpg',10,?,'2025-01-01')
        """, (s_id, title, handle, price, comp, avail))
    conn.commit()
    conn.close()
    yield
    if db_path.exists():
        db_path.unlink()


class TestGroqFallbackDetection:
    @pytest.mark.asyncio
    async def test_no_client_returns_error(self):
        result = await groq_chat("hello", [])
        assert "not configured" in result["answer"].lower()

    def test_extract_keywords_removes_stopwords(self):
        kw = extract_keywords("What new products do you have?")
        assert "new" in kw
        assert "what" not in kw


class TestExecuteTool:
    def test_search_new_products_returns_list(self):
        result = execute_tool("search_new_products", {})
        assert isinstance(result, list)

    def test_search_best_sellers_returns_list(self):
        result = execute_tool("search_best_sellers", {})
        assert isinstance(result, list)

    def test_search_deals_returns_list(self):
        result = execute_tool("search_deals", {})
        assert isinstance(result, list)

    def test_search_deals_in_collection_with_bad_handle(self):
        result = execute_tool("search_deals_in_collection", {"handle": "nonexistent"})
        assert isinstance(result, list)

    def test_unknown_tool_returns_none(self):
        result = execute_tool("nonexistent_tool", {})
        assert result is None


class TestCollectProducts:
    def test_collect_products_includes_compare_at_price(self):
        products = []
        sample = [{"title": "Test", "price": 100.0, "compare_at_price": 150.0,
                    "image_url": "", "handle": "test", "available": True,
                    "first_variant_id": "v1", "short_description": "desc"}]
        collect_products_from_result(sample, products)
        assert len(products) == 1
        assert products[0]["compare_at_price"] == 150.0

    def test_collect_products_defaults_compare_at_to_zero(self):
        products = []
        sample = [{"title": "Test", "price": 100.0, "image_url": "",
                    "handle": "test", "available": True,
                    "first_variant_id": "v1", "short_description": "desc"}]
        collect_products_from_result(sample, products)
        assert products[0].get("compare_at_price") == 0


class TestParsePriceLimit:
    def test_under_1000(self):
        assert parse_price_limit("show me products under 1000") == 1000.0

    def test_budget_500(self):
        assert parse_price_limit("budget 500 rupees") == 500.0

    def test_no_price(self):
        assert parse_price_limit("show me pet wipes") == 0.0
