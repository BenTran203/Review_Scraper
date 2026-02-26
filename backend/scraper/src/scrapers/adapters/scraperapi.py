"""
ScraperAPI adapter — pluggable replacement for custom scrapers.

Enable by setting SCRAPER_ADAPTER=scraperapi and providing SCRAPERAPI_KEY.
ScraperAPI handles proxy rotation, CAPTCHA solving, and IP management.
See: https://www.scraperapi.com/
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from ..base import IReviewScraper, Review
from ...utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)


class ScraperAPIScraper(IReviewScraper):
    """
    Generic scraper that routes requests through ScraperAPI's proxy.
    Works for any supported platform by rendering the page via ScraperAPI
    and parsing the resulting HTML with Beautiful Soup.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.scraperapi.com"

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.api_key:
            logger.error("ScraperAPI key is not configured")
            return []

        reviews: list[Review] = []

        params = {
            "api_key": self.api_key,
            "url": url,
            "render": "true",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code != 200:
                    logger.warning("ScraperAPI returned %d for %s", resp.status_code, url)
                    return []

                soup = BeautifulSoup(resp.text, "lxml")

                # Generic review extraction — adjust selectors per platform as needed
                review_elements = soup.select(
                    '[data-hook="review"], .review-item, .shopee-product-rating, .review-card'
                )

                for el in review_elements[:max_reviews]:
                    text = el.get_text(strip=True)
                    if text:
                        reviews.append(Review(
                            text=sanitize_text(text[:1000]),
                            rating=3.0,
                            date="",
                        ))

            except Exception as e:
                logger.error("ScraperAPI error: %s", e)

        return reviews[:max_reviews]
