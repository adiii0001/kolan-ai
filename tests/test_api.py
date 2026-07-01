import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path("C:/Users/Aditya Verma/OneDrive/Desktop/AIKolan project/kolan-ai")))
os.environ["DATABASE_URL"] = str(pathlib.Path(__file__).parent / "test_kolan_api.db")

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    db_path = pathlib.Path(__file__).parent / "test_kolan_api.db"
    if db_path.exists():
        db_path.unlink()
    from app.core.database import init_db, get_connection
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    products = [
        ("pw1", "Kolan Pet Wipes 60 Count", "pet-wipes", 330.0, 395.0, 1,
         "Gentle pet wipes for daily grooming", "pet-wipes"),
        ("pw2", "Kolan Pet Wipes Pack of 2",
         "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-2",
         599.0, 790.0, 1, "Value pack pet wipes", "pet-wipes"),
        ("cl1", "Kolan Floor Cleaner", "no-rinse-floor-cleaner", 489.0, 495.0, 1,
         "Streak-free floor cleaner", "cleaner"),
        ("cl2", "Kolan Bathroom Cleaner", "bathroom-cleaner", 389.0, 395.0, 1,
         "Eco-friendly bathroom cleaner", "cleaner"),
        ("cl3", "Kolan Kitchen Cleaner", "kitchen-cleaner", 389.0, 395.0, 1,
         "Kitchen grease cleaner", "cleaner"),
        ("cl4", "Kolan Glass Cleaner", "no-streak-glass-cleaner", 389.0, 395.0, 1,
         "Streak-free glass cleaner", "cleaner"),
    ]
    for s_id, title, handle, price, comp, avail, desc, ptype in products:
        cursor.execute("""
            INSERT INTO products (shopify_id, title, handle, description, price,
                compare_at_price, first_variant_id, vendor, product_type, tags,
                image_url, inventory_quantity, available, shopify_created_at)
            VALUES (?,?,?,?,?,?,'v1','Kolan',?,'', 'img.jpg', 10, ?, '2025-01-01')
        """, (s_id, title, handle, desc, price, comp, ptype, avail))
    conn.commit()
    conn.close()
    yield
    if db_path.exists():
        db_path.unlink()


transport = ASGITransport(app=app)


@pytest.mark.asyncio
class TestChatEndpoint:
    async def test_chat_with_new_products_query(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "What new products do you have?",
                "context": {"pageType": "collection", "collection": {"title": "Pet Care", "handle": "pet-wipes"}}
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data
            assert "products" in data

    async def test_chat_with_best_sellers_query(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "Show me best-selling products",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data

    async def test_chat_with_offers_query(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "What offers and deals are available?",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data

    async def test_chat_with_deals_in_collection(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "What is the best deal in this collection?",
                "context": {"pageType": "collection", "collection": {"title": "Pet Care", "handle": "pet-wipes"}}
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data

    async def test_chat_products_have_compare_at_price(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "show me pet wipes",
            })
            assert resp.status_code == 200
            data = resp.json()
            if data.get("products"):
                for p in data["products"]:
                    assert "compare_at_price" in p

    async def test_chat_without_context_works(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "Hello",
            })
            assert resp.status_code == 200

    async def test_chat_with_collection_context(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={
                "message": "What products are in this collection?",
                "context": {"pageType": "collection", "collection": {"title": "Pet Care", "handle": "pet-wipes"}}
            })
            assert resp.status_code == 200
