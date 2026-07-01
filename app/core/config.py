import os

from pydantic_settings import BaseSettings
from typing import List


_ENV_VARS_TO_STRIP = [
    "GROQ_API_KEY",
    "CLAUDE_API_KEY",
    "OPENAI_API_KEY",
    "SHOPIFY_WEBHOOK_SECRET",
    "DATABASE_URL",
]

for _key in _ENV_VARS_TO_STRIP:
    _raw = os.environ.get(_key)
    if _raw:
        # Take only the last line (Vercel env vars sometimes get leading garbage)
        os.environ[_key] = _raw.splitlines()[-1].strip()


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
