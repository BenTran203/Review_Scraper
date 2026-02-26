"""eBay review scraper using httpx + Beautiful Soup."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .base import IReviewScraper, Review
from ..utils.rate_limiter import RateLimiter
from ..utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(domain="ebay.com", delay=1.5)


class EbayScraper(IReviewScraper):
    """Scrapes eBay product reviews using Playwright."""

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.check_robots_txt(url):
            logger.warning("Skipping eBay scrape — blocked by robots.txt")
            return []

        reviews: list[Review] = []
        review_url = self._build_review_url(url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="ReviewPulseBot/1.0 (educational project; respects robots.txt)"
            )
            page = await context.new_page()

            page_num = 1
            while len(reviews) < max_reviews:
                await rate_limiter.wait()

                paginated = f"{review_url}&pgn={page_num}" if page_num > 1 else review_url
                logger.info("Scraping eBay page %d: %s", page_num, paginated)

                try:
                    await page.goto(paginated, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)

                    content = await page.content()
                    page_reviews = self._parse_reviews(content)

                    if not page_reviews:
                        break

                    reviews.extend(page_reviews)
                    page_num += 1
                except Exception as e:
                    logger.error("eBay scrape error page %d: %s", page_num, e)
                    break

            await browser.close()

        return reviews[:max_reviews]

    def _build_review_url(self, product_url: str) -> str:
        """Convert a product URL to its reviews page."""
        item_match = re.search(r'/itm/(\d+)', product_url)
        if item_match:
            item_id = item_match.group(1)
            return f"https://www.ebay.com/urw/product-reviews/{item_id}"
        # Fallback: try to find reviews link from the page
        return product_url

    def _parse_reviews(self, html: str) -> list[Review]:
        """Parse review data from an eBay reviews page."""
        soup = BeautifulSoup(html, "lxml")
        reviews = []

        review_cards = soup.select(".review-item, .ebay-review-section .review-card")
        for card in review_cards:
            try:
                # Rating
                rating_el = card.select_one(".star-rating, [aria-label*='out of 5']")
                rating = 3.0
                if rating_el:
                    label = rating_el.get("aria-label", "") or rating_el.get_text()
                    match = re.search(r'(\d+(?:\.\d+)?)', label)
                    if match:
                        rating = float(match.group(1))

                # Review text
                text_el = card.select_one(".review-item-content p, .review-text")
                text = sanitize_text(text_el.get_text(strip=True)) if text_el else ""

                # Date
                date_el = card.select_one(".review-item-date, .review-date")
                date = date_el.get_text(strip=True) if date_el else ""

                if text:
                    reviews.append(Review(text=text, rating=rating, date=date))
            except Exception as e:
                logger.debug("Failed to parse eBay review: %s", e)
                continue

        return reviews
