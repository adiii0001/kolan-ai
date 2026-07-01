import os, sys, pathlib, sqlite3
sys.path.insert(0, str(pathlib.Path("C:/Users/Aditya Verma/OneDrive/Desktop/AIKolan project/kolan-ai")))
os.environ["DATABASE_URL"] = str(pathlib.Path(__file__).parent / "test_kolan.db")

import pytest
from app.tools.search_catalog import (
    _row_to_dict, search_new_products, search_best_sellers,
    search_deals, search_deals_in_collection, search_catalog, search_available,
)
from app.core.database import get_connection, init_db


@pytest.fixture(autouse=True)
def setup_db():
    db_path = pathlib.Path(__file__).parent / "test_kolan.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    products = [
        ("pw1", "Kolan Pet Wipes 60 Count (Pack of 1)", "pet-wipes", 330.0, 395.0, 1, "", "pet-wipes"),
        ("pw2", "Kolan Pet Wipes Pack of 2", "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-2", 599.0, 790.0, 1, "", "pet-wipes"),
        ("pw5", "Kolan Pet Wipes Pack of 5", "kolan-pet-wipes-grooming-wipes-for-dogs-cats-60-count-pack-of-5", 1290.0, 1975.0, 1, "", "pet-wipes"),
        ("pw12", "Kolan Pet Wipes Pack of 12", "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-12", 2795.0, 4740.0, 1, "", "pet-wipes"),
        ("cl1", "Kolan Floor Cleaner", "no-rinse-floor-cleaner", 489.0, 495.0, 1, "Floor Cleaner", "cleaner"),
        ("cl2", "Kolan Bathroom Cleaner", "bathroom-cleaner", 389.0, 395.0, 1, "", "cleaner"),
        ("cl3", "Kolan Kitchen Cleaner", "kitchen-cleaner", 389.0, 395.0, 1, "", "cleaner"),
        ("cl4", "Kolan Glass Cleaner", "no-streak-glass-cleaner", 389.0, 395.0, 1, "", "cleaner"),
        ("cl5", "Kolan All Purpose Cleaner", "all-purpose-surface-spray", 389.0, 395.0, 1, "", "cleaner"),
        ("cl6", "Kolan Laundry Detergent", "laundry-detergent", 389.0, 395.0, 1, "", "cleaner"),
        ("cl7", "Kolan Farm Cleaner 5L", "farm-stable-cleaner", 3485.0, 3495.0, 0, "", "cleaner"),
    ]
    for s_id, title, handle, price, comp, avail, ptype, tags in products:
        cursor.execute("""
            INSERT INTO products (shopify_id, title, handle, description, price,
                compare_at_price, first_variant_id, vendor, product_type, tags,
                image_url, inventory_quantity, available, shopify_created_at)
            VALUES (?,?,?,'desc',?,?,'v1','Kolan',?,?,'img.jpg',10,?,'2025-01-01')
        """, (s_id, title, handle, price, comp, ptype, tags, avail))
    conn.commit()
    conn.close()
    yield
    db_path = pathlib.Path(__file__).parent / "test_kolan.db"
    if db_path.exists():
        db_path.unlink()


class TestCuratedCollections:
    def test_search_new_products_returns_6_products(self):
        result = search_new_products()
        assert len(result) == 6

    def test_search_new_products_includes_two_pet_wipes(self):
        result = search_new_products()
        titles = [r["title"] for r in result]
        wipe_count = sum(1 for t in titles if "Pet Wipe" in t or "pet-wipe" in t)
        assert wipe_count >= 2, f"Expected at least 2 pet wipes, got {wipe_count}: {titles}"

    def test_search_new_products_includes_cleaners(self):
        result = search_new_products()
        handles = [r["handle"] for r in result]
        assert "no-rinse-floor-cleaner" in handles
        assert "bathroom-cleaner" in handles or "kitchen-cleaner" in handles

    def test_search_new_products_only_in_stock(self):
        result = search_new_products()
        for r in result:
            assert r["available"] is True, f"{r['title']} is out of stock"

    def test_search_best_sellers_returns_6_products(self):
        result = search_best_sellers()
        assert len(result) == 6

    def test_search_best_sellers_includes_two_pet_wipes(self):
        result = search_best_sellers()
        titles = [r["title"] for r in result]
        wipe_count = sum(1 for t in titles if "Pet Wipe" in t or "pet-wipe" in t)
        assert wipe_count >= 2, f"Expected at least 2 pet wipes, got {wipe_count}"

    def test_search_best_sellers_includes_discounted_products(self):
        result = search_best_sellers()
        discounted = [r for r in result if r.get("compare_at_price", 0) > r["price"]]
        assert len(discounted) >= 2, "Expected at least 2 discounted products in best sellers"


class TestSearchDeals:
    def test_search_deals_returns_discounted_products(self):
        result = search_deals()
        assert len(result) > 0
        for r in result:
            assert r["compare_at_price"] > r["price"]

    def test_search_deals_ordered_by_discount_desc(self):
        result = search_deals(limit=5)
        discounts = [r["compare_at_price"] - r["price"] for r in result]
        assert discounts == sorted(discounts, reverse=True)

    def test_search_deals_includes_compare_at_price(self):
        result = search_deals(limit=1)
        assert result[0]["compare_at_price"] > 0


class TestSearchDealsInCollection:
    def test_search_deals_in_collection_returns_empty_for_bad_handle(self):
        result = search_deals_in_collection("nonexistent-collection-handle")
        assert isinstance(result, list)

    def test_search_deals_in_collection_filters_discounted(self):
        result = search_deals_in_collection("pet-wipes")
        assert isinstance(result, list)
        for r in result:
            assert r["compare_at_price"] > r["price"]


class TestCatalogSearch:
    def test_search_catalog_returns_matching_products(self):
        result = search_catalog("bathroom")
        assert any("Bathroom" in r["title"] for r in result)

    def test_search_available_excludes_oos(self):
        result = search_available("farm")
        for r in result:
            assert r["available"] is True

    def test_search_catalog_includes_compare_at_price(self):
        result = search_catalog("pet wipes")
        for r in result:
            assert "compare_at_price" in r


class TestRowToDict:
    def test_row_to_dict_has_all_fields(self):
        conn = get_connection()
        row = conn.execute("SELECT * FROM products LIMIT 1").fetchone()
        conn.close()
        d = _row_to_dict(row)
        assert "title" in d
        assert "price" in d
        assert "compare_at_price" in d
        assert "handle" in d
        assert "image_url" in d
        assert "available" in d
        assert "short_description" in d
