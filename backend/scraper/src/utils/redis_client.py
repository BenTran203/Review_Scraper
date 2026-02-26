"""Redis client wrapper for the scraper service."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

import redis

logger = logging.getLogger(__name__)


class RedisClient:
    """Simple Redis client for storing scrape progress and results."""

    def __init__(self, redis_url: str):
        parsed = urlparse(redis_url)
        self.client = redis.Redis(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password or None,
            db=0,
            decode_responses=True,
        )

    def update_status(self, token: str, status: str) -> None:
        """Update the session status in Redis."""
        key = f"session:{token}:meta"
        raw = self.client.get(key)
        if raw:
            data = json.loads(raw)
            data["status"] = status
            ttl = self.client.ttl(key)
            self.client.set(key, json.dumps(data), ex=max(ttl, 60))

    def store_reviews(self, token: str, reviews: list[dict]) -> None:
        """Store scraped reviews in Redis."""
        key = f"session:{token}:reviews"
        meta_key = f"session:{token}:meta"
        ttl = self.client.ttl(meta_key)
        self.client.set(key, json.dumps(reviews), ex=max(ttl, 3600))

    def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return self.client.ping()
        except Exception:
            return False
