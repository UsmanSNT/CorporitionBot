import logging
from app.models import WatchRule, Listing
from app.utils.transliterate import keyword_matches

logger = logging.getLogger(__name__)


def matches_rule(listing: Listing, rule: WatchRule) -> bool:
    """Return True if listing matches the watch rule filters."""

    # Keyword — script-independent match (Latin/Cyrillic/Russian)
    if rule.keyword:
        title = listing.title or ""
        desc = listing.description or ""
        seller = listing.seller_name or ""
        if not (keyword_matches(rule.keyword, title)
                or keyword_matches(rule.keyword, desc)
                or keyword_matches(rule.keyword, seller)):
            return False

    # Price filters
    if rule.max_price is not None and listing.price is not None:
        if listing.price > rule.max_price:
            return False

    if rule.min_price is not None and listing.price is not None:
        if listing.price < rule.min_price:
            return False

    # Quantity filters
    if rule.min_quantity is not None and listing.quantity is not None:
        if listing.quantity < rule.min_quantity:
            return False

    if rule.max_quantity is not None and listing.quantity is not None:
        if listing.quantity > rule.max_quantity:
            return False

    # Region filter
    if rule.region and rule.region.lower() not in ("barchasi", "all", "все"):
        if listing.region:
            if rule.region.lower() not in listing.region.lower():
                return False

    # Source filter
    if rule.source and rule.source != "both":
        if listing.source != rule.source:
            return False

    # Seller filter
    if rule.seller:
        if not listing.seller_name:
            return False
        if rule.seller.lower() not in listing.seller_name.lower():
            return False

    return True


def find_matching_rules(listing: Listing, rules: list[WatchRule]) -> list[WatchRule]:
    """Return all enabled rules that match the listing."""
    return [r for r in rules if r.enabled and matches_rule(listing, r)]
