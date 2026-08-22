"""
xt-xarid.uz (Hayot Birja) source adapter.

Uses the site's internal JSON-RPC 2.0 API at https://api.xt-xarid.uz/rpc
with public reference endpoints discovered by reverse engineering the SPA.
No authentication required for public procedure data.
"""
import logging
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources.base import BaseSource, ListingData
from app.utils.text import make_hash

logger = logging.getLogger(__name__)

BASE_URL = "https://xt-xarid.uz"
API_URL = "https://api.xt-xarid.uz/rpc"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://xt-xarid.uz",
    "User-Agent": "Mozilla/5.0 (compatible; cooperation-watcher-bot/1.0)",
}

# Public reference endpoints for different procedure types
PUBLIC_REFS = [
    "ref_tender_public",
    "ref_selection_public",
    "ref_request_proposals_public",
    "ref_contest_public",
]

STATUS_LABELS = {
    "open": "Ochiq",
    "docs_objections": "Hujjatlar muhokamasi",
    "closed": "Yopiq",
    "cancelled": "Bekor qilindi",
    "finished": "Yakunlandi",
}


class XtXaridSource(BaseSource):
    name = "xt_xarid"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=20.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _rpc(self, ref: str, limit: int = 20) -> list[dict]:
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "ref",
            "params": {"ref": ref, "op": "read", "limit": limit},
        }
        response = await self.client.post(API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        if "result" in data and isinstance(data["result"], list):
            return data["result"]
        if "error" in data:
            logger.warning(f"xt-xarid.uz {ref}: {data['error'].get('message', '')[:100]}")
        return []

    def _to_listing(self, item: dict) -> Optional[ListingData]:
        proc_id = item.get("id")
        name = item.get("name", "").strip()
        if not proc_id or not name:
            return None

        totalcost = item.get("totalcost")
        price = int(totalcost) if totalcost is not None else None
        currency = item.get("currency", "USD")

        status_code = item.get("status", "")
        status_label = STATUS_LABELS.get(status_code, status_code)

        proc_type = item.get("type", "tender")
        close_at = item.get("close_at", "")
        close_str = f", muddat: {close_at}" if close_at else ""

        description = f"Tur: {proc_type} | Holat: {status_label} | Valyuta: {currency}{close_str}"

        company = (item.get("company_name") or "").strip()
        region = item.get("area")

        pub_str = item.get("publicated_at")
        published_at = None
        if pub_str:
            try:
                published_at = datetime.fromisoformat(pub_str)
            except (ValueError, TypeError):
                pass

        lot_count = item.get("lot_count")
        quantity = int(lot_count) if lot_count else None

        source_url = f"{BASE_URL}/procedure/{proc_id}/core"
        raw = make_hash(f"{proc_id}{name}{totalcost}{status_code}")

        return ListingData(
            external_id=str(proc_id),
            source=self.name,
            title=name,
            description=description,
            price=price,
            currency=currency,
            quantity=quantity,
            seller_name=company or None,
            region=str(region) if region else None,
            published_at=published_at,
            source_url=source_url,
            raw_data_hash=raw,
        )

    async def get_latest(self, page: int = 1) -> list[ListingData]:
        limit = 20
        all_listings: list[ListingData] = []
        seen_ids: set[str] = set()

        for ref in PUBLIC_REFS:
            try:
                items = await self._rpc(ref, limit=limit)
                for item in items:
                    listing = self._to_listing(item)
                    if listing and listing.external_id not in seen_ids:
                        seen_ids.add(listing.external_id)
                        all_listings.append(listing)
                logger.debug(f"xt-xarid.uz {ref}: {len(items)} items")
            except Exception as e:
                logger.error(f"xt-xarid.uz {ref} failed: {e}")

        logger.info(f"xt-xarid.uz get_latest: {len(all_listings)} total listings")
        return all_listings

    async def search(self, keyword: str, page: int = 1) -> list[ListingData]:
        kw = keyword.lower()
        all_listings = await self.get_latest(page=page)
        matched = [
            l for l in all_listings
            if kw in (l.title or "").lower()
            or kw in (l.description or "").lower()
            or kw in (l.seller_name or "").lower()
        ]
        logger.info(f"xt-xarid.uz search '{keyword}': {len(matched)}/{len(all_listings)}")
        return matched

    async def get_item(self, external_id: str) -> Optional[ListingData]:
        # Try to find in any public ref by fetching a larger set
        try:
            for ref in PUBLIC_REFS:
                items = await self._rpc(ref, limit=50)
                for item in items:
                    if str(item.get("id")) == external_id:
                        return self._to_listing(item)
        except Exception as e:
            logger.error(f"xt-xarid.uz get_item {external_id}: {e}")
        return None

    async def health_check(self) -> bool:
        try:
            items = await self._rpc("ref_tender_public", limit=1)
            return isinstance(items, list)
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.aclose()
