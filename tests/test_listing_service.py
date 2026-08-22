import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.sources.base import ListingData
from app.services.listing_service import upsert_listing


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def make_data(**kwargs) -> ListingData:
    defaults = dict(
        external_id="123", source="cooperation",
        title="Test Mahsulot", price=1000000,
        currency="UZS", raw_data_hash="abc123",
    )
    defaults.update(kwargs)
    return ListingData(**defaults)


def test_new_listing(session):
    data = make_data()
    listing, is_new, price_changed = upsert_listing(session, data)
    assert is_new is True
    assert price_changed is False
    assert listing.external_id == "123"


def test_no_duplicate(session):
    data = make_data()
    _, is_new1, _ = upsert_listing(session, data)
    _, is_new2, _ = upsert_listing(session, data)
    assert is_new1 is True
    assert is_new2 is False


def test_price_change_detected(session):
    data = make_data(price=1000000)
    listing, _, _ = upsert_listing(session, data)

    updated = make_data(price=800000, raw_data_hash="xyz")
    _, is_new, price_changed = upsert_listing(session, updated)

    assert is_new is False
    assert price_changed is True
    assert listing.price == 800000
