"""
Oxylabs adapter — pluggable replacement for custom scrapers.

Enable by setting SCRAPER_ADAPTER=oxylabs and providing OXYLABS_USER/OXYLABS_PASS.
Oxylabs provides e-commerce-specific scraping with structured data output.
See: https://oxylabs.io/
"""

from __future__ import annotations

import logging

import httpx

from ..base import IReviewScraper, Review
from ...utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)


class OxylabsScraper(IReviewScraper):
    """
    Scraper that uses Oxylabs' Realtime Crawler to fetch e-commerce reviews.
    Returns structured data so no HTML parsing is needed.
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://realtime.oxylabs.io/v1/queries"

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.username or not self.password:
            logger.error("Oxylabs credentials are not configured")
            return []

        reviews: list[Review] = []

        payload = {
            "source": "universal_ecommerce",
            "url": url,
            "render": "html",
            "parse": True,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    self.base_url,
                    json=payload,
                    auth=(self.username, self.password),
                )

                if resp.status_code != 200:
                    logger.warning("Oxylabs returned %d for %s", resp.status_code, url)
                    return []

                data = resp.json()
                results = data.get("results", [])

                for result in results:
                    content = result.get("content", {})
                    review_list = content.get("reviews", [])
                    for r in review_list[:max_reviews]:
                        text = r.get("body", "") or r.get("content", "")
                        if text:
                            reviews.append(Review(
                                text=sanitize_text(text),
                                rating=float(r.get("rating", 3)),
                                date=str(r.get("date", "")),
                            ))

            except Exception as e:
                logger.error("Oxylabs error: %s", e)

        return reviews[:max_reviews]
