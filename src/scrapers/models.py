from typing import Optional
from pydantic import BaseModel, Field

class PromoItem(BaseModel):
    id: Optional[str] = None
    store_id: str
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    original_price: Optional[float] = None
    promo_price: Optional[float] = None
    discount_text: Optional[str] = None
    unit_info: Optional[str] = None
    image_url: Optional[str] = None
    deal_url: Optional[str] = None
    category_id: str = "pantry"
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

    def to_dict(self):
        return self.model_dump()
