import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.wishlist import WishlistItem
from app.routers.auth import get_current_user
from app.schemas.wishlist import (
    ProductLookupResult,
    WishlistItemCreate,
    WishlistItemOut,
    WishlistItemUpdate,
    WishlistStats,
)

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


# ---------------------------------------------------------------------------
# Product lookup
# ---------------------------------------------------------------------------

def _extract_store(url: str) -> str | None:
    try:
        host = urlparse(url).hostname or ""
        host = host.removeprefix("www.")
        # Friendly names for common stores
        mapping = {
            "amazon.es": "Amazon",
            "amazon.com": "Amazon",
            "amazon.co.uk": "Amazon",
            "amazon.de": "Amazon",
            "amazon.fr": "Amazon",
            "fnac.es": "Fnac",
            "pccomponentes.com": "PCComponentes",
            "mediamarkt.es": "MediaMarkt",
            "elcorteingles.es": "El Corte Inglés",
            "zara.com": "Zara",
            "zalando.es": "Zalando",
            "apple.com": "Apple",
            "steam.com": "Steam",
            "steampowered.com": "Steam",
            "ebay.es": "eBay",
            "ebay.com": "eBay",
        }
        return mapping.get(host) or host.split(".")[0].capitalize()
    except Exception:
        return None


def _parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    # Remove currency symbols, spaces, and normalise decimal separators
    cleaned = re.sub(r"[^\d.,]", "", raw).strip()
    if not cleaned:
        return None
    # If both comma and dot present, the last one is the decimal separator
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Could be thousands or decimal — if 2-3 digits after comma → decimal
        parts = cleaned.split(",")
        if len(parts[-1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


async def _lookup_product(url: str) -> ProductLookupResult:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    title: str | None = None
    price: float | None = None
    image_url: str | None = None
    store = _extract_store(url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=10, headers=headers
        ) as client:
            r = await client.get(url)
            html = r.text

        # --- JSON-LD (most reliable when present) ---
        for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
            try:
                data = json.loads(match.group(1))
                # data can be a list or single object
                items = data if isinstance(data, list) else [data]
                for obj in items:
                    if obj.get("@type") in ("Product", "Book", "SoftwareApplication"):
                        title = title or obj.get("name")
                        image = obj.get("image")
                        if isinstance(image, list):
                            image_url = image_url or (image[0] if image else None)
                        elif isinstance(image, str):
                            image_url = image_url or image
                        offers = obj.get("offers") or obj.get("Offers")
                        if offers:
                            if isinstance(offers, list):
                                offers = offers[0]
                            raw_price = offers.get("price") or offers.get("lowPrice")
                            price = price or _parse_price(str(raw_price))
            except Exception:
                pass

        # --- Open Graph / meta tags fallback ---
        def _meta(prop: str) -> str | None:
            m = re.search(
                rf'<meta[^>]+(?:property|name)=["\'](?:og:)?{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.IGNORECASE
            ) or re.search(
                rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:)?{re.escape(prop)}["\']',
                html, re.IGNORECASE
            )
            return m.group(1).strip() if m else None

        title = title or _meta("title") or _meta("og:title")
        image_url = image_url or _meta("image") or _meta("og:image")

        # Try common price meta patterns
        if not price:
            for prop in ("price:amount", "product:price:amount", "price", "og:price:amount"):
                raw = _meta(prop)
                if raw:
                    price = _parse_price(raw)
                    if price:
                        break

        # Fallback: look for itemprop="price"
        if not price:
            m = re.search(r'itemprop=["\']price["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not m:
                m = re.search(r'content=["\']([^"\']+)["\'][^>]+itemprop=["\']price["\']', html, re.IGNORECASE)
            if m:
                price = _parse_price(m.group(1))

        # Fallback: <title> tag
        if not title:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()

    except Exception:
        pass

    return ProductLookupResult(
        title=title,
        price=price,
        image_url=image_url,
        store=store,
        url=url,
    )


@router.get("/lookup", response_model=ProductLookupResult)
async def lookup_product(url: str):
    return await _lookup_product(url)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=WishlistStats)
def get_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(WishlistItem).where(WishlistItem.user_id == current_user.id)
    ).all()

    pending   = [i for i in items if not i.purchased and not i.gifted]
    purchased = [i for i in items if i.purchased and not i.gifted]
    gifted    = [i for i in items if i.gifted]

    return WishlistStats(
        total_items=len(items),
        pending_items=len(pending),
        purchased_items=len(purchased),
        gifted_items=len(gifted),
        total_cost=round(sum(i.price or 0 for i in items), 2),
        pending_cost=round(sum(i.price or 0 for i in pending), 2),
        purchased_cost=round(sum(i.price or 0 for i in purchased), 2),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[WishlistItemOut])
def list_items(
    purchased: bool | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(WishlistItem).where(WishlistItem.user_id == current_user.id)
    if purchased is not None:
        q = q.where(WishlistItem.purchased == purchased)
    q = q.order_by(WishlistItem.created_at.desc())
    return db.scalars(q).all()


@router.post("", response_model=WishlistItemOut, status_code=201)
def create_item(
    body: WishlistItemCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = WishlistItem(user_id=current_user.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=WishlistItemOut)
def update_item(
    item_id: int,
    body: WishlistItemUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/purchase", response_model=WishlistItemOut)
def purchase_item(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    item.purchased = True
    item.purchased_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/gift", response_model=WishlistItemOut)
def gift_item(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    item.gifted = True
    item.purchased = False
    item.purchased_at = None
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/ungift", response_model=WishlistItemOut)
def ungift_item(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    item.gifted = False
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/unpurchase", response_model=WishlistItemOut)
def unpurchase_item(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    item.purchased = False
    item.purchased_at = None
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(WishlistItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.delete(item)
    db.commit()
