import logging
import re
import json
from typing import Optional
from urllib.parse import urljoin
from datetime import datetime

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

# Pages to monitor on new.cooperation.uz
MONITOR_PATHS = [
    "/plan-schedule",
    "/catalog",
    "/products",
    "/lot",
    "/lots",
    "/tender",
    "/auction",
]


class NewCooperationSource(BaseSource):
    name = "new_cooperation"

    def __init__(self) -> None:
        self.base_url = config.NEW_COOPERATION_BASE_URL
        self.client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=30.0,
            follow_redirects=True,
        )
        self._working_paths: list[str] = []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch(self, url: str, params: dict | None = None) -> str:
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.text

    async def _discover_working_paths(self) -> list[str]:
        """Find which paths actually return content."""
        if self._working_paths:
            return self._working_paths

        working = []
        for path in MONITOR_PATHS:
            url = f"{self.base_url}{path}"
            try:
                response = await self.client.get(url, timeout=10.0)
                if response.status_code == 200:
                    working.append(path)
                    logger.info(f"new.cooperation.uz: path {path} is accessible")
            except Exception:
                pass

        self._working_paths = working or ["/plan-schedule"]
        return self._working_paths

    def _parse_plan_schedule(self, html: str) -> list[ListingData]:
        """Parse the plan-schedule page for procurement plans."""
        soup = BeautifulSoup(html, "lxml")
        listings = []

        # Try table rows (procurement plans are often in tables)
        rows = soup.find_all("tr")
        for i, row in enumerate(rows):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            texts = [c.get_text(strip=True) for c in cells]

            # Skip header rows
            if all(not t or t.isdigit() is False for t in texts[:2]):
                first = texts[0].lower()
                if any(w in first for w in ["nomi", "name", "наим", "№", "#"]):
                    continue

            title = next((t for t in texts if len(t) > 5), None)
            if not title:
                continue

            # Try to find price in cells
            price = None
            for t in texts:
                p = parse_price(t)
                if p and p > 1000:
                    price = p
                    break

            external_id = f"ps_{i}_{make_hash(title)[:8]}"
            link_tag = row.find("a")
            source_url = urljoin(self.base_url, link_tag["href"]) if link_tag else f"{self.base_url}/plan-schedule"

            listings.append(ListingData(
                external_id=external_id,
                source=self.name,
                title=title,
                price=price,
                currency="UZS",
                source_url=source_url,
                raw_data_hash=make_hash("".join(texts)),
            ))

        if listings:
            logger.debug(f"new.cooperation.uz: parsed {len(listings)} rows from plan-schedule")
            return listings

        # Fallback: card-based layout
        return self._parse_cards(soup)

    def _parse_cards(self, soup: BeautifulSoup) -> list[ListingData]:
        """Generic card parser for any listing page."""
        listings = []
        selectors = [
            ".product-item", ".product_item", ".catalog-item",
            ".lot-item", ".tender-item", ".card", ".item",
            "[class*='product']", "[class*='lot']", "[class*='item']",
        ]

        cards = []
        for sel in selectors:
            found = soup.select(sel)
            if len(found) >= 2:
                cards = found
                break

        for i, card in enumerate(cards):
            try:
                title_tag = card.find(["h1", "h2", "h3", "h4", "h5", ".title", ".name"])
                title = title_tag.get_text(strip=True) if title_tag else card.get_text(strip=True)[:100]
                if not title or len(title) < 3:
                    continue

                price_tag = card.find(class_=re.compile(r"price|narx|cost|summa"))
                price = parse_price(price_tag.get_text(strip=True)) if price_tag else None

                link_tag = card.find("a", href=True)
                href = link_tag["href"] if link_tag else ""
                source_url = urljoin(self.base_url, href) if href else self.base_url

                # Extract ID from URL if possible
                id_match = re.search(r"/(\d+)/?$", href)
                external_id = id_match.group(1) if id_match else f"card_{i}_{make_hash(title)[:8]}"

                seller_tag = card.find(class_=re.compile(r"seller|company|tashkilot"))
                seller = seller_tag.get_text(strip=True) if seller_tag else None

                region_tag = card.find(class_=re.compile(r"region|viloyat|location"))
                region = region_tag.get_text(strip=True) if region_tag else None

                listings.append(ListingData(
                    external_id=external_id,
                    source=self.name,
                    title=title,
                    price=price,
                    seller_name=seller,
                    region=region,
                    source_url=source_url,
                    raw_data_hash=make_hash(f"{external_id}{title}{price}"),
                ))
            except Exception as e:
                logger.debug(f"new.cooperation.uz: card parse error: {e}")

        return listings

    async def get_latest(self, page: int = 1) -> list[ListingData]:
        paths = await self._discover_working_paths()
        all_listings = []

        for path in paths[:3]:  # Check up to 3 working paths
            try:
                url = f"{self.base_url}{path}"
                params = {"page": page} if page > 1 else None
                html = await self._fetch(url, params)

                if path == "/plan-schedule":
                    listings = self._parse_plan_schedule(html)
                else:
                    soup = BeautifulSoup(html, "lxml")
                    listings = self._parse_cards(soup)

                all_listings.extend(listings)
                logger.info(f"new.cooperation.uz: {path} → {len(listings)} listings")
            except Exception as e:
                logger.error(f"new.cooperation.uz get_latest {path} failed: {e}")

        return all_listings

    async def search(self, keyword: str, page: int = 1) -> list[ListingData]:
        # Try common search URL patterns
        search_urls = [
            f"{self.base_url}/search?q={keyword}",
            f"{self.base_url}/products/search?query={keyword}",
            f"{self.base_url}/catalog?search={keyword}",
            f"{self.base_url}/plan-schedule?search={keyword}",
        ]

        for url in search_urls:
            try:
                html = await self._fetch(url)
                soup = BeautifulSoup(html, "lxml")
                listings = self._parse_cards(soup)
                if listings:
                    logger.info(f"new.cooperation.uz: search '{keyword}' at {url} → {len(listings)}")
                    return listings
            except Exception as e:
                logger.debug(f"new.cooperation.uz search URL {url} failed: {e}")

        # Fallback: get latest and filter in memory
        all_listings = await self.get_latest(page)
        filtered = [l for l in all_listings if keyword.lower() in l.title.lower()]
        logger.info(f"new.cooperation.uz: in-memory search '{keyword}' → {len(filtered)}/{len(all_listings)}")
        return filtered

    async def get_item(self, external_id: str) -> Optional[ListingData]:
        # Try to reconstruct the URL from external_id
        if external_id.isdigit():
            for path in ["/products/product", "/lot", "/catalog/item"]:
                url = f"{self.base_url}{path}/{external_id}"
                try:
                    html = await self._fetch(url)
                    soup = BeautifulSoup(html, "lxml")
                    title_tag = soup.find(["h1", "h2"])
                    title = title_tag.get_text(strip=True) if title_tag else f"Item {external_id}"
                    price_tag = soup.find(class_=re.compile(r"price|narx"))
                    price = parse_price(price_tag.get_text(strip=True)) if price_tag else None
                    return ListingData(
                        external_id=external_id,
                        source=self.name,
                        title=title,
                        price=price,
                        source_url=url,
                        raw_data_hash=make_hash(f"{external_id}{title}{price}"),
                    )
                except Exception:
                    continue
        return None

    async def health_check(self) -> bool:
        try:
            response = await self.client.get(
                f"{self.base_url}/plan-schedule", timeout=10.0
            )
            return response.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.aclose()
