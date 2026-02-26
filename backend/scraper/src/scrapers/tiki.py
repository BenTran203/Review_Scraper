"""Tiki review scraper using httpx (Tiki has a well-structured public API)."""

from __future__ import annotations

import logging
import re

import httpx

from .base import IReviewScraper, Review
from ..utils.rate_limiter import RateLimiter
from ..utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(domain="tiki.vn", delay=1.0)


class TikiScraper(IReviewScraper):
    """
    Scrapes Tiki.vn reviews via their public review API.
    Tiki exposes a relatively open JSON API for product reviews.
    """

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.check_robots_txt(url):
            logger.warning("Skipping Tiki scrape — blocked by robots.txt")
            return []

        product_id = self._extract_product_id(url)
        if not product_id:
            logger.warning("Could not extract product ID from Tiki URL: %s", url)
            return []

        reviews: list[Review] = []
        page = 1
        limit = 20

        headers = {
            "User-Agent": "ReviewPulseBot/1.0 (educational project; respects robots.txt)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            while len(reviews) < max_reviews:
                await rate_limiter.wait()

                api_url = (
                    f"https://tiki.vn/api/v2/reviews"
                    f"?product_id={product_id}&page={page}&limit={limit}"
                    f"&sort=score|desc,id|desc,stars|all"
                )

                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        logger.warning("Tiki API returned %d", resp.status_code)
                        break

                    data = resp.json()
                    items = data.get("data", [])
                    if not items:
                        break

                    for item in items:
                        content = item.get("content", "")
                        if content:
                            reviews.append(Review(
                                text=sanitize_text(content),
                                rating=float(item.get("rating", 3)),
                                date=str(item.get("created_at", "")),
                            ))

                    # Check if there are more pages
                    paging = data.get("paging", {})
                    last_page = paging.get("last_page", 1)
                    if page >= last_page:
                        break

                    page += 1
                except Exception as e:
                    logger.warning("Tiki API error: %s", e)
                    break

        return reviews[:max_reviews]

    def _extract_product_id(self, url: str) -> str | None:
        """Extract product ID from Tiki URL (e.g., p12345678.html)."""
        match = re.search(r'p(\d+)', url)
        return match.group(1) if match else None
