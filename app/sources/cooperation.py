import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import config
from app.sources.base import BaseSource, ListingData
from app.utils.money import parse_price
from app.utils.text import make_hash

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class CooperationSource(BaseSource):
    name = "cooperation"

    def __init__(self) -> None:
        self.base_url = config.COOPERATION_BASE_URL
        self.client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=30.0,
            follow_redirects=True,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch(self, url: str, params: dict | None = None) -> str:
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.text

    def _parse_listings(self, html: str, base_url: str) -> list[ListingData]:
        soup = BeautifulSoup(html, "lxml")
        listings = []

        # Try multiple common product card selectors
        selectors = [
            ".product-item", ".product_item", ".catalog-item",
            ".product-card", ".item-card", ".goods-item",
            "[class*='product']", "[class*='catalog']", "[class*='item']",
        ]

        cards = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                cards = found
                logger.debug(f"cooperation.uz: found {len(found)} cards with selector '{sel}'")
                break

        if not cards:
            # Fallback: any <a> link pointing to /products/product/
            cards = soup.find_all("a", href=re.compile(r"/products/product/\d+"))
            logger.debug(f"cooperation.uz: found {len(cards)} product links (fallback)")

        for card in cards:
            try:
                listing = self._parse_card(card, base_url)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"cooperation.uz: skipping card due to error: {e}")

        return listings

    def _parse_card(self, card, base_url: str) -> Optional[ListingData]:
        # Extract link and ID
        link_tag = card if card.name == "a" else card.find("a", href=re.compile(r"/products/product/"))
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        match = re.search(r"/products/product/(\d+)", href)
        if not match:
            return None

        external_id = match.group(1)
        source_url = urljoin(base_url, href)

        # Title
        title_tag = card.find(["h1", "h2", "h3", "h4", ".product-name", ".name", ".title"])
        title = title_tag.get_text(strip=True) if title_tag else link_tag.get_text(strip=True)
        if not title:
            return None

        # Price
        price_tag = card.find(class_=re.compile(r"price|narx|cost"))
        price_raw = price_tag.get_text(strip=True) if price_tag else None
        price = parse_price(price_raw)

        # Seller
        seller_tag = card.find(class_=re.compile(r"seller|company|firm|ishlab"))
        seller = seller_tag.get_text(strip=True) if seller_tag else None

        # Region
        region_tag = card.find(class_=re.compile(r"region|location|viloyat|hudud"))
        region = region_tag.get_text(strip=True) if region_tag else None

        # Quantity
        qty_tag = card.find(class_=re.compile(r"qty|quantity|miqdor|amount"))
        quantity = None
        if qty_tag:
            qty_text = qty_tag.get_text(strip=True)
            qty_match = re.search(r"\d+", qty_text)
            if qty_match:
                quantity = int(qty_match.group())

        # Image
        img_tag = card.find("img")
        image_url = urljoin(base_url, img_tag.get("src", "")) if img_tag else None

        raw_data = f"{external_id}{title}{price}{seller}"
        return ListingData(
            external_id=external_id,
            source=self.name,
            title=title,
            price=price,
            currency="UZS",
            seller_name=seller,
            region=region,
            quantity=quantity,
            source_url=source_url,
            image_url=image_url if image_url and image_url != base_url else None,
            raw_data_hash=make_hash(raw_data),
        )

    async def get_latest(self, page: int = 1) -> list[ListingData]:
        try:
            url = f"{self.base_url}/products/search"
            params = {"query": "", "catalog": "", "page": page}
            html = await self._fetch(url, params)
            listings = self._parse_listings(html, self.base_url)
            logger.info(f"cooperation.uz: fetched {len(listings)} listings (page {page})")
            return listings
        except Exception as e:
            logger.error(f"cooperation.uz get_latest failed: {e}")
            return []

    async def search(self, keyword: str, page: int = 1) -> list[ListingData]:
        try:
            url = f"{self.base_url}/products/search"
            params = {"query": keyword, "catalog": "", "page": page}
            html = await self._fetch(url, params)
            listings = self._parse_listings(html, self.base_url)
            logger.info(f"cooperation.uz: search '{keyword}' → {len(listings)} listings")
            return listings
        except Exception as e:
            logger.error(f"cooperation.uz search failed for '{keyword}': {e}")
            return []

    async def get_item(self, external_id: str) -> Optional[ListingData]:
        try:
            url = f"{self.base_url}/products/product/{external_id}"
            html = await self._fetch(url)
            soup = BeautifulSoup(html, "lxml")

            title_tag = soup.find(["h1", "h2"])
            title = title_tag.get_text(strip=True) if title_tag else f"Product {external_id}"

            price_tag = soup.find(class_=re.compile(r"price|narx"))
            price = parse_price(price_tag.get_text(strip=True)) if price_tag else None

            raw_data = f"{external_id}{title}{price}"
            return ListingData(
                external_id=external_id,
                source=self.name,
                title=title,
                price=price,
                source_url=url,
                raw_data_hash=make_hash(raw_data),
            )
        except Exception as e:
            logger.error(f"cooperation.uz get_item {external_id} failed: {e}")
            return None

    async def health_check(self) -> bool:
        try:
            response = await self.client.get(self.base_url, timeout=10.0)
            return response.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.aclose()
