from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ListingData:
    external_id: str
    source: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[int] = None
    currency: str = "UZS"
    quantity: Optional[int] = None
    minimum_quantity: Optional[int] = None
    seller_name: Optional[str] = None
    seller_id: Optional[str] = None
    region: Optional[str] = None
    mxik: Optional[str] = None
    tif_tn: Optional[str] = None
    published_at: Optional[datetime] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    raw_data_hash: Optional[str] = None


class BaseSource(ABC):
    name: str = "base"

    @abstractmethod
    async def get_latest(self, page: int = 1) -> list[ListingData]:
        """Fetch latest listings from source."""
        ...

    @abstractmethod
    async def search(self, keyword: str, page: int = 1) -> list[ListingData]:
        """Search listings by keyword."""
        ...

    @abstractmethod
    async def get_item(self, external_id: str) -> Optional[ListingData]:
        """Fetch single listing by external ID."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if source is reachable."""
        ...
