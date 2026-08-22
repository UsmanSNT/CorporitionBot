import logging
from sqlalchemy.orm import Session
from app.models import Listing, PriceHistory

logger = logging.getLogger(__name__)


def get_price_history(session: Session, listing_id: int) -> list[PriceHistory]:
    return (
        session.query(PriceHistory)
        .filter_by(listing_id=listing_id)
        .order_by(PriceHistory.recorded_at.desc())
        .all()
    )


def get_previous_price(session: Session, listing_id: int) -> int | None:
    history = (
        session.query(PriceHistory)
        .filter_by(listing_id=listing_id)
        .order_by(PriceHistory.recorded_at.desc())
        .offset(1)
        .first()
    )
    return history.price if history else None
