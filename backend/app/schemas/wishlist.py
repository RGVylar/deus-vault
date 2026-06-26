from datetime import datetime

from pydantic import BaseModel


class WishlistItemCreate(BaseModel):
    title: str
    url: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    notes: str | None = None
    source_id: str | None = None


class WishlistItemUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    notes: str | None = None
    source_id: str | None = None


class WishlistItemOut(BaseModel):
    id: int
    title: str
    url: str | None
    price: float | None
    image_url: str | None
    store: str | None
    notes: str | None
    source_id: str | None
    purchased: bool
    purchased_at: datetime | None
    gifted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WishlistStats(BaseModel):
    total_items: int
    pending_items: int
    purchased_items: int
    gifted_items: int
    total_cost: float
    pending_cost: float
    purchased_cost: float


class ProductLookupResult(BaseModel):
    title: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    url: str | None = None
    source_id: str | None = None
    content_type_hint: str | None = None
