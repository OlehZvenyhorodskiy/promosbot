from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class PromoItem(BaseModel):
    id: Optional[str] = None
    fingerprint: Optional[str] = None
    store_id: str
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    brand: Optional[str] = None
    original_price: Optional[float] = None
    promo_price: Optional[float] = None
    discount_text: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    price_per_unit: Optional[float] = None
    unit_info: Optional[str] = None
    image_url: Optional[str] = None
    deal_url: Optional[str] = None
    category_id: str = "pantry"
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    leaflet_id: Optional[str] = None
    page_number: Optional[int] = None
    coordinates: Optional[Dict[str, Any]] = None
    source_type: str = "web"

    def calculate_discount_percentage(self) -> Optional[float]:
        if self.original_price and self.promo_price and self.original_price > self.promo_price:
            return round(((self.original_price - self.promo_price) / self.original_price) * 100, 1)
        return None

    def to_dict(self):
        return self.model_dump()
