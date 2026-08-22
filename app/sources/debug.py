"""
Run with:
  python -m app.sources.debug
  python -m app.sources.debug cooperation
  python -m app.sources.debug new
"""
import asyncio
import sys
import json
from dataclasses import asdict

from app.utils.logging import setup_logging
from app.config import config


async def debug_source(name: str) -> None:
    if name == "cooperation":
        from app.sources.cooperation import CooperationSource
        source = CooperationSource()
    elif name in ("new", "new_cooperation"):
        from app.sources.new_cooperation import NewCooperationSource
        source = NewCooperationSource()
    else:
        print(f"Unknown source: {name}")
        return

    print(f"\n{'='*50}")
    print(f"Source: {source.name}")
    print(f"{'='*50}")

    ok = await source.health_check()
    print(f"Health check: {'✅ OK' if ok else '❌ FAILED'}")

    if ok:
        listings = await source.get_latest(page=1)
        print(f"get_latest(): {len(listings)} listings")
        if listings:
            first = listings[0]
            print(f"\nSample listing:")
            print(f"  ID:     {first.external_id}")
            print(f"  Title:  {first.title}")
            print(f"  Price:  {first.price} {first.currency}")
            print(f"  Seller: {first.seller_name}")
            print(f"  URL:    {first.source_url}")

    await source.close()


async def main() -> None:
    setup_logging()
    sources = sys.argv[1:] or ["cooperation", "new"]
    for name in sources:
        await debug_source(name)


if __name__ == "__main__":
    asyncio.run(main())
