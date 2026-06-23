from pydantic import BaseModel
from typing import Optional


class Policy(BaseModel):
    id: Optional[int] = None
    policy_type: str
    title: str
    content: str = ""
    updated_at: Optional[str] = None
