import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Listing, PriceHistory
from app.sources.base import ListingData

logger = logging.getLogger(__name__)


def upsert_listing(session: Session, data: ListingData) -> tuple[Listing, bool, bool]:
    """
    Insert or update a listing.
    Returns (listing, is_new, price_changed).
    """
    existing = (
        session.query(Listing)
        .filter_by(source=data.source, external_id=data.external_id)
        .first()
    )

    if existing is None:
        listing = Listing(
            source=data.source,
            external_id=data.external_id,
            title=data.title,
            description=data.description,
            category=data.category,
            price=data.price,
            currency=data.currency or "UZS",
            quantity=data.quantity,
            minimum_quantity=data.minimum_quantity,
            seller_name=data.seller_name,
            seller_id=data.seller_id,
            region=data.region,
            mxik=data.mxik,
            tif_tn=data.tif_tn,
            published_at=data.published_at,
            source_url=data.source_url,
            image_url=data.image_url,
            raw_data_hash=data.raw_data_hash,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        session.add(listing)
        session.flush()

        if data.price is not None:
            session.add(PriceHistory(listing_id=listing.id, price=data.price))

        logger.debug(f"New listing: [{data.source}] {data.external_id} '{data.title}'")
        return listing, True, False

    # Update existing
    price_changed = (
        data.price is not None
        and existing.price is not None
        and existing.price != data.price
    )

    if price_changed:
        session.add(PriceHistory(listing_id=existing.id, price=data.price))
        logger.info(
            f"Price change: [{data.source}] {data.external_id} "
            f"{existing.price} → {data.price}"
        )

    existing.title = data.title
    existing.price = data.price
    existing.currency = data.currency or existing.currency
    existing.quantity = data.quantity
    existing.seller_name = data.seller_name
    existing.region = data.region
    existing.source_url = data.source_url
    existing.raw_data_hash = data.raw_data_hash
    existing.last_seen_at = datetime.utcnow()

    return existing, False, price_changed


def get_cheapest(session: Session, keyword: str | None = None, limit: int = 10) -> list[Listing]:
    q = session.query(Listing).filter(Listing.price.isnot(None))
    if keyword:
        q = q.filter(Listing.title.ilike(f"%{keyword}%"))
    return q.order_by(Listing.price.asc()).limit(limit).all()


def get_latest_listings(session: Session, source: str | None = None, limit: int = 20) -> list[Listing]:
    q = session.query(Listing)
    if source:
        q = q.filter(Listing.source == source)
    return q.order_by(Listing.first_seen_at.desc()).limit(limit).all()


def search_listings(session: Session, keyword: str, limit: int = 20) -> list[Listing]:
    return (
        session.query(Listing)
        .filter(Listing.title.ilike(f"%{keyword}%"))
        .order_by(Listing.first_seen_at.desc())
        .limit(limit)
        .all()
    )


def get_stats(session: Session) -> dict:
    total = session.query(Listing).count()
    notifs = session.query(Listing).count()  # placeholder
    return {"total_listings": total}
