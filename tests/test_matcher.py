import pytest
from app.models import WatchRule, Listing
from app.services.matcher import matches_rule


def make_rule(**kwargs) -> WatchRule:
    defaults = dict(
        id=1, user_id=1, name="Test", keyword="konditsioner",
        max_price=None, min_price=None, min_quantity=None,
        max_quantity=None, region=None, seller=None,
        source=None, enabled=True,
        notify_new=True, notify_price_drop=True,
    )
    defaults.update(kwargs)
    rule = WatchRule()
    for k, v in defaults.items():
        setattr(rule, k, v)
    return rule


def make_listing(**kwargs) -> Listing:
    defaults = dict(
        id=1, source="cooperation", external_id="123",
        title="Konditsioner Artel 12", price=3000000,
        currency="UZS", quantity=5, region="Toshkent",
        seller_name="ABC LLC",
    )
    defaults.update(kwargs)
    lst = Listing()
    for k, v in defaults.items():
        setattr(lst, k, v)
    return lst


def test_keyword_match():
    rule = make_rule(keyword="konditsioner")
    listing = make_listing(title="Konditsioner Artel 12")
    assert matches_rule(listing, rule)


def test_keyword_case_insensitive():
    rule = make_rule(keyword="KONDITSIONER")
    listing = make_listing(title="konditsioner samsung")
    assert matches_rule(listing, rule)


def test_keyword_no_match():
    rule = make_rule(keyword="noutbuk")
    listing = make_listing(title="Konditsioner Artel")
    assert not matches_rule(listing, rule)


def test_max_price_filter():
    rule = make_rule(keyword="konditsioner", max_price=2000000)
    listing = make_listing(price=3000000)
    assert not matches_rule(listing, rule)


def test_max_price_pass():
    rule = make_rule(keyword="konditsioner", max_price=4000000)
    listing = make_listing(price=3000000)
    assert matches_rule(listing, rule)


def test_region_filter():
    rule = make_rule(keyword="konditsioner", region="Samarqand")
    listing = make_listing(region="Toshkent")
    assert not matches_rule(listing, rule)


def test_region_barchasi():
    rule = make_rule(keyword="konditsioner", region="Barchasi")
    listing = make_listing(region="Toshkent")
    assert matches_rule(listing, rule)


def test_source_filter():
    rule = make_rule(keyword="konditsioner", source="cooperation")
    listing = make_listing(source="new_cooperation")
    assert not matches_rule(listing, rule)
