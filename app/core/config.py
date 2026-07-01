import os

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    groq_api_key: str = ""
    claude_api_key: str = ""
    openai_api_key: str = ""
    shopify_webhook_secret: str = ""
    database_url: str = "data/kolan.db"
    allowed_origins: List[str] = [
        "http://localhost:8000",
        "https://kolan.co.in",
        "https://www.kolan.co.in",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Strip whitespace from all string settings (protects against env var corruption)
for _field in settings.model_fields:
    _val = getattr(settings, _field, None)
    if isinstance(_val, str):
        setattr(settings, _field, _val.strip())
