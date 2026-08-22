import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Listing, PriceHistory
from app.services.price_service import get_price_history, get_previous_price
from datetime import datetime


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_price_history(session):
    listing = Listing(
        source="cooperation", external_id="1",
        title="Test", price=1000000,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    session.add(listing)
    session.flush()

    session.add(PriceHistory(listing_id=listing.id, price=1200000))
    session.add(PriceHistory(listing_id=listing.id, price=1000000))
    session.flush()

    history = get_price_history(session, listing.id)
    assert len(history) == 2


def test_previous_price(session):
    listing = Listing(
        source="cooperation", external_id="2",
        title="Test2", price=900000,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    session.add(listing)
    session.flush()

    session.add(PriceHistory(listing_id=listing.id, price=1100000))
    session.add(PriceHistory(listing_id=listing.id, price=900000))
    session.flush()

    prev = get_previous_price(session, listing.id)
    assert prev == 1100000
