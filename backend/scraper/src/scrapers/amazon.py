"""Amazon review scraper using Playwright + Beautiful Soup with stealth."""

from __future__ import annotations

import asyncio
import logging
import random
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from .base import IReviewScraper, Review
from ..utils.rate_limiter import RateLimiter
from ..utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(domain="amazon.com", delay=1.0)

# JavaScript to patch headless detection fingerprints
STEALTH_JS = """
() => {
    // Override navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // Override navigator.plugins to look like a real browser
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // Override navigator.languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
    });

    // Override chrome runtime
    window.chrome = { runtime: {} };

    // Override permissions query
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
}
"""


async def _stealth_page(page: Page) -> None:
    """Apply stealth patches to a Playwright page to avoid bot detection."""
    await page.add_init_script(STEALTH_JS)


class AmazonScraper(IReviewScraper):
    """Scrapes Amazon product reviews from the product detail page using Playwright."""

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.check_robots_txt(url):
            logger.warning("Skipping Amazon scrape — blocked by robots.txt")
            return []

        reviews: list[Review] = []
        product_url = self._normalize_product_url(url)

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
                java_script_enabled=True,
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            page = await context.new_page()
            await _stealth_page(page)

            try:
                logger.info("Loading Amazon product page: %s", product_url)
                await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(random.randint(3000, 5000))

                # Check for bot detection
                title = await page.title()
                logger.info("Amazon product page title: '%s'", title)
                content_lower = (await page.content()).lower()
                if "captcha" in content_lower or "amazon sign-in" in title.lower():
                    logger.warning("Amazon blocked access (title: '%s') — stopping", title)
                    await browser.close()
                    return []

                # Scroll to bottom progressively to trigger lazy-loaded content
                logger.info("Scrolling through page to load reviews...")
                page_height = await page.evaluate("document.body.scrollHeight")
                scroll_pos = 0
                while scroll_pos < page_height:
                    scroll_pos += 500
                    await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                    await page.wait_for_timeout(random.randint(300, 600))
                    # Recheck page height as content loads
                    page_height = await page.evaluate("document.body.scrollHeight")

                # Scroll back to reviews section
                await page.evaluate("""
                    const el = document.querySelector('#reviewsMedley')
                        || document.querySelector('#cm-cr-dp-review-list')
                        || document.querySelector('[data-hook="top-customer-reviews-widget"]');
                    if (el) el.scrollIntoView({ block: 'center' });
                """)
                await page.wait_for_timeout(2000)

                # Debug: check what exists in the DOM
                debug_info = await page.evaluate("""() => {
                    const reviewHook = document.querySelectorAll('[data-hook="review"]').length;
                    const reviewClass = document.querySelectorAll('.review').length;
                    const reviewLi = document.querySelectorAll('li.review').length;
                    const crList = document.querySelector('#cm-cr-dp-review-list');
                    const medley = document.querySelector('#reviewsMedley');
                    // Check for reviews in iframes
                    const iframes = document.querySelectorAll('iframe').length;
                    // Check for shadow roots
                    const allEls = document.querySelectorAll('*');
                    let shadowRoots = 0;
                    allEls.forEach(e => { if (e.shadowRoot) shadowRoots++; });
                    return {
                        reviewHook, reviewClass, reviewLi,
                        hasCrList: !!crList,
                        hasMedley: !!medley,
                        iframes, shadowRoots,
                        bodyLen: document.body.innerHTML.length,
                    };
                }""")
                logger.info("DOM debug: %s", debug_info)

                # Save debug HTML for inspection
                content = await page.content()
                try:
                    with open("amazon_debug.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info("Saved debug HTML (%d chars) to amazon_debug.html", len(content))
                except Exception:
                    pass

                # Parse reviews
                reviews = self._parse_reviews(content)
                logger.info("Found %d reviews on product page", len(reviews))

                # If we got reviews from the product page but need more,
                # try loading additional review pages via AJAX-style pagination
                if reviews and len(reviews) < max_reviews:
                    await self._load_more_reviews(page, reviews, max_reviews)

            except Exception as e:
                logger.error("Amazon scrape error: %s", e)
            finally:
                await browser.close()

        return reviews[:max_reviews]

    async def _load_more_reviews(self, page, reviews: list[Review], max_reviews: int) -> None:
        """Try to load more reviews by clicking pagination within the page."""
        for attempt in range(5):
            if len(reviews) >= max_reviews:
                break

            try:
                # Look for "Next page" button in the reviews section
                next_btn = page.locator('li.a-last a, [data-hook="pagination-bar"] a:has-text("Next")')
                if await next_btn.count() == 0:
                    break

                await next_btn.first.click()
                await page.wait_for_timeout(random.randint(2000, 4000))

                content = await page.content()
                new_reviews = self._parse_reviews(content)
                if not new_reviews:
                    break

                reviews.extend(new_reviews)
                logger.info("Loaded %d total reviews after pagination click %d", len(reviews), attempt + 1)
            except Exception as e:
                logger.debug("Pagination attempt %d failed: %s", attempt + 1, e)
                break

    def _normalize_product_url(self, url: str) -> str:
        """Ensure we have a clean product detail page URL (/dp/ASIN)."""
        asin = self._extract_asin(url)
        if asin:
            domain_match = re.search(r'(amazon\.\w+(?:\.\w+)?)', url)
            domain = domain_match.group(1) if domain_match else "amazon.com"
            return f"https://www.{domain}/dp/{asin}"
        return url

    def _extract_asin(self, url: str) -> str | None:
        """Extract ASIN from any Amazon URL format."""
        # /dp/ASIN or /product-reviews/ASIN
        match = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', url)
        return match.group(1) if match else None

    def _parse_reviews(self, html: str) -> list[Review]:
        """Parse review data from an Amazon page (product page or reviews page)."""
        soup = BeautifulSoup(html, "lxml")
        reviews = []

        # Match both <div> and <li> elements with data-hook="review"
        review_els = soup.select('[data-hook="review"]')
        logger.debug("Found %d elements with [data-hook='review']", len(review_els))

        for el in review_els:
            try:
                # Rating — try multiple selector patterns
                rating = 3.0
                rating_el = (
                    el.select_one('[data-hook="review-star-rating"] .a-icon-alt')
                    or el.select_one('[data-hook="cmps-review-star-rating"] .a-icon-alt')
                    or el.select_one('.a-icon-alt')
                )
                if rating_el:
                    match = re.search(r'(\d+(?:\.\d+)?)', rating_el.get_text())
                    if match:
                        rating = float(match.group(1))

                # Review text — try multiple selector patterns
                body_el = (
                    el.select_one('[data-hook="review-collapsed"]')
                    or el.select_one('[data-hook="review-body"] span')
                    or el.select_one('.review-text-content')
                    or el.select_one('.reviewText')
                )
                text = sanitize_text(body_el.get_text(strip=True)) if body_el else ""

                # Date
                date_el = el.select_one('[data-hook="review-date"]')
                date = date_el.get_text(strip=True) if date_el else ""

                if text:
                    reviews.append(Review(text=text, rating=rating, date=date))
            except Exception as e:
                logger.debug("Failed to parse Amazon review: %s", e)
                continue

        return reviews
