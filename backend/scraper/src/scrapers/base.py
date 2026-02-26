"""Base scraper interface and shared utilities."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Review:
    """A single customer review."""
    text: str
    rating: float
    date: str

    def to_dict(self) -> dict:
        return asdict(self)


class IReviewScraper(ABC):
    """
    Pluggable adapter interface for review scraping.

    Implementations:
      - Custom scrapers (Playwright + BS4) — free, default
      - Third-party adapters (ScraperAPI, Oxylabs) — paid, swap-in via config
    """

    @abstractmethod
    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        """
        Scrape reviews from the given product URL.

        Args:
            url: Full product URL.
            max_reviews: Maximum number of reviews to return.

        Returns:
            List of Review objects.
        """
        ...

    @staticmethod
    def check_robots_txt(url: str) -> bool:
        """
        Check whether the given URL is allowed by the site's robots.txt.

        Returns True if scraping is allowed or if robots.txt cannot be fetched.
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)

            # Fetch with a short timeout
            resp = httpx.get(robots_url, timeout=5, follow_redirects=True)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                allowed = rp.can_fetch("ReviewPulseBot", url)
                if not allowed:
                    logger.warning("robots.txt DISALLOWS scraping: %s", url)
                return allowed

            # If robots.txt is not found (404), assume allowed
            return True
        except Exception as e:
            logger.warning("Could not check robots.txt for %s: %s", url, e)
            # Fail open: allow scraping if we can't read robots.txt
            return True
