import os

from pydantic_settings import BaseSettings
from typing import List


def _should_load_dotenv() -> bool:
    return os.environ.get("VERCEL") != "1"


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
        env_file = ".env" if _should_load_dotenv() else None
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Strip leading/trailing whitespace from all string values (fixes Vercel
        # env var corruption where stray newlines get prepended to values)
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if isinstance(value, str):
                setattr(self, field_name, value.strip())


settings = Settings()
