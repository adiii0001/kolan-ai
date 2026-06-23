from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    id: Optional[int] = None
    shopify_id: str
    title: str
    handle: str = ""
    description: str = ""
    price: float = 0.0
    compare_at_price: Optional[float] = 0.0
    vendor: str = ""
    product_type: str = ""
    tags: str = ""
    image_url: str = ""
    inventory_quantity: int = 0
    available: bool = True


class ProductCard(BaseModel):
    title: str
    price: float
    image_url: str
    handle: str
    available: bool
