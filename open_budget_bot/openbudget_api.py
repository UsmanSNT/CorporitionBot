import time
import logging
import urllib.request
import json

logger = logging.getLogger(__name__)

_cache: dict = {"count": None, "ts": 0.0}
CACHE_TTL = 600  # 10 daqiqa


def fetch_vote_count(uuid: str) -> int | None:
    now = time.time()
    if _cache["count"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["count"]
    try:
        url = f"https://new.openbudget.uz/api/v1/initiatives/{uuid}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        count = data.get("vote_count")
        if count is not None:
            _cache["count"] = int(count)
            _cache["ts"] = now
            logger.info(f"OpenBudget vote_count: {count}")
            return _cache["count"]
    except Exception as e:
        logger.warning(f"OpenBudget API error: {e}")
    return _cache["count"]
