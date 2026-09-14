"""Declarative configuration model for Belgian retail stores and supermarkets."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from src.core.constants import SUPERMARKETS


class StoreConfig(BaseModel):
    id: str
    name: str
    emoji: str = "🏪"
    url: str
    folder_url: str
    color: str = "#333333"
    loyalty_card: Optional[str] = None
    api_endpoint: Optional[str] = None
    enabled: bool = True
    publitas_id: Optional[str] = None
    tiendeo_slug: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoreConfig":
        return cls(**data)

    @classmethod
    def get_all(cls) -> List["StoreConfig"]:
        return [cls.from_dict(info) for info in SUPERMARKETS.values()]

    @classmethod
    def get(cls, store_id: str) -> Optional["StoreConfig"]:
        info = SUPERMARKETS.get(store_id)
        if not info:
            return None
        return cls.from_dict(info)

    @classmethod
    def get_loyalty_card(cls, store_id: str) -> Optional[str]:
        info = SUPERMARKETS.get(store_id)
        return info.get("loyalty_card") if info else None
