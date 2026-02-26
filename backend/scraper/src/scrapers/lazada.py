"""Lazada review scraper using httpx (internal API) with Playwright fallback."""

from __future__ import annotations

import logging
import random
import re

import httpx
from playwright.async_api import async_playwright, Page

from .base import IReviewScraper, Review
from ..utils.rate_limiter import RateLimiter
from ..utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(domain="lazada.vn", delay=1.0)

STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi'] });
    window.chrome = { runtime: {} };
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
}
"""


async def _stealth_page(page: Page) -> None:
    await page.add_init_script(STEALTH_JS)


class LazadaScraper(IReviewScraper):
    """
    Scrapes Lazada reviews via internal API with Playwright fallback.
    Similar to Shopee, Lazada uses an internal JSON endpoint for reviews.
    """

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.check_robots_txt(url):
            logger.warning("Skipping Lazada scrape — blocked by robots.txt")
            return []

        item_id = self._extract_item_id(url)
        if item_id:
            reviews = await self._scrape_via_api(item_id, max_reviews, url)
            if reviews:
                return reviews[:max_reviews]

        return await self._fallback_playwright(url, max_reviews)

    def _extract_item_id(self, url: str) -> str | None:
        """Extract item ID from Lazada URL (e.g., -i12345678.html)."""
        match = re.search(r'-i(\d+)', url)
        return match.group(1) if match else None

    def _get_domain(self, url: str) -> str:
        """Extract Lazada domain (supports multiple country TLDs)."""
        match = re.search(r'(lazada\.\w+(?:\.\w+)?)', url)
        return match.group(1) if match else "lazada.vn"

    async def _scrape_via_api(self, item_id: str, max_reviews: int, original_url: str) -> list[Review]:
        """Attempt to fetch reviews from Lazada's internal review API."""
        reviews: list[Review] = []
        domain = self._get_domain(original_url)
        page = 1

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": original_url,
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            while len(reviews) < max_reviews:
                await rate_limiter.wait()

                api_url = (
                    f"https://my.{domain}/pdp/review/getReviewList"
                    f"?itemId={item_id}&pageSize=50&pageNo={page}"
                )

                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        logger.warning("Lazada API returned %d for page %d", resp.status_code, page)
                        break

                    content_type = resp.headers.get("content-type", "")
                    if "json" not in content_type:
                        logger.warning(
                            "Lazada returned non-JSON response (content-type: %s) — likely anti-bot page. "
                            "First 200 chars: %s",
                            content_type, resp.text[:200],
                        )
                        break

                    data = resp.json()
                    items = data.get("model", {}).get("items", [])
                    if not items:
                        break

                    for item in items:
                        text = item.get("reviewContent", "")
                        if text:
                            reviews.append(Review(
                                text=sanitize_text(text),
                                rating=float(item.get("rating", 3)),
                                date=str(item.get("reviewTime", "")),
                            ))

                    page += 1
                except Exception as e:
                    logger.warning("Lazada API error: %s", e)
                    break

        return reviews

    async def _fallback_playwright(self, url: str, max_reviews: int) -> list[Review]:
        """Fallback: use Playwright to scrape reviews from rendered page."""
        reviews: list[Review] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9,vi;q=0.8"},
            )
            page = await context.new_page()
            await _stealth_page(page)

            try:
                logger.info("Loading Lazada product page: %s", url)
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(random.randint(2000, 3000))

                title = await page.title()
                logger.info("Lazada page title: '%s'", title)

                # Scroll through page to trigger lazy loading
                page_height = await page.evaluate("document.body.scrollHeight")
                scroll_pos = 0
                while scroll_pos < page_height:
                    scroll_pos += 500
                    await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                    await page.wait_for_timeout(random.randint(200, 400))
                    page_height = await page.evaluate("document.body.scrollHeight")

                await page.wait_for_timeout(2000)

                content = await page.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, "lxml")

                # Try multiple selectors for Lazada review elements
                review_items = (
                    soup.select(".review-content")
                    or soup.select(".item-content")
                    or soup.select("[class*='review-item']")
                    or soup.select("[class*='mod-reviews'] .item")
                )

                logger.info("Lazada: found %d review elements via Playwright", len(review_items))

                for item in review_items[:max_reviews]:
                    text_el = (
                        item.select_one(".content")
                        or item.select_one(".review-content-text")
                        or item.select_one("[class*='content']")
                    )
                    text = sanitize_text(text_el.get_text(strip=True)) if text_el else ""

                    rating_el = item.select_one("[class*='star']")
                    rating = 3.0

                    if text:
                        reviews.append(Review(text=text, rating=rating, date=""))
            except Exception as e:
                logger.error("Lazada Playwright fallback error: %s", e)
            finally:
                await browser.close()

        return reviews
