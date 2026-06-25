from datetime import datetime

from pydantic import BaseModel


class WishlistItemCreate(BaseModel):
    title: str
    url: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    notes: str | None = None


class WishlistItemUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    notes: str | None = None


class WishlistItemOut(BaseModel):
    id: int
    title: str
    url: str | None
    price: float | None
    image_url: str | None
    store: str | None
    notes: str | None
    purchased: bool
    purchased_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WishlistStats(BaseModel):
    total_items: int
    pending_items: int
    purchased_items: int
    total_cost: float
    pending_cost: float
    purchased_cost: float


class ProductLookupResult(BaseModel):
    title: str | None = None
    price: float | None = None
    image_url: str | None = None
    store: str | None = None
    url: str | None = None
