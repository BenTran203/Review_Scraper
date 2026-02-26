"""Shopee review scraper using httpx (internal JSON API) with Playwright fallback.

Strategy:
  1. Try internal ratings API first (fast, often blocked with 403).
  2. Fallback to Playwright with comprehensive stealth:
     a. Block Shopee's pcmall-anticrawler script via route interception.
     b. Intercept XHR responses to capture review JSON from network.
     c. Pre-warm session by visiting Shopee homepage first.
     d. Parse rendered HTML as last resort.
"""

from __future__ import annotations

import json
import logging
import random
import re

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, BrowserContext, Route

from .base import IReviewScraper, Review
from ..utils.rate_limiter import RateLimiter
from ..utils.sanitizer import sanitize_text

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(domain="shopee.vn", delay=1.0)

# Comprehensive stealth script — spoofs all common fingerprinting vectors
STEALTH_JS = """
() => {
    // 1. Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;

    // 2. Fake plugins array (Chrome normally has 5)
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Chromium PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
            ];
            plugins.refresh = () => {};
            plugins.item = (i) => plugins[i] || null;
            plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
            return plugins;
        }
    });

    // 3. Languages
    Object.defineProperty(navigator, 'languages', { get: () => ['vi', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'language', { get: () => 'vi' });

    // 4. Chrome runtime
    window.chrome = {
        runtime: { onConnect: { addListener: () => {}, removeListener: () => {} },
                   onMessage: { addListener: () => {}, removeListener: () => {} },
                   sendMessage: () => {} },
        loadTimes: () => ({ requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000,
                            commitLoadTime: Date.now() / 1000, finishDocumentLoadTime: Date.now() / 1000,
                            finishLoadTime: Date.now() / 1000, firstPaintTime: Date.now() / 1000,
                            firstPaintAfterLoadTime: 0, navigationType: 'Other',
                            wasFetchedViaSpdy: true, wasNpnNegotiated: true,
                            npnNegotiatedProtocol: 'h2', wasAlternateProtocolAvailable: false,
                            connectionInfo: 'h2' }),
        csi: () => ({ pageT: Date.now(), startE: Date.now(), onloadT: Date.now(), tran: 15 }),
        app: { isInstalled: false, InstallState: { INSTALLED: 'installed', NOT_INSTALLED: 'not_installed', DISABLED: 'disabled' },
               getIsInstalled: () => false, getDetails: () => null, runningState: () => 'cannot_run' },
    };

    // 5. Permissions query
    const origPermQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : origPermQuery(params);

    // 6. WebGL vendor/renderer (typical Intel GPU)
    const getParameterProxyHandler = {
        apply: function(target, thisArg, args) {
            const param = args[0];
            if (param === 37445) return 'Intel Inc.';           // UNMASKED_VENDOR_WEBGL
            if (param === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
            return target.apply(thisArg, args);
        }
    };
    const origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = new Proxy(origGetParam, getParameterProxyHandler);
    if (typeof WebGL2RenderingContext !== 'undefined') {
        const origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = new Proxy(origGetParam2, getParameterProxyHandler);
    }

    // 7. Canvas fingerprint noise
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        if (this.width > 16 && this.height > 16) {
            const ctx = this.getContext('2d');
            if (ctx) {
                const style = ctx.fillStyle;
                ctx.fillStyle = 'rgba(255,255,255,0.01)';
                ctx.fillRect(0, 0, 1, 1);
                ctx.fillStyle = style;
            }
        }
        return origToDataURL.apply(this, arguments);
    };

    // 8. Connection (typical broadband)
    Object.defineProperty(navigator, 'connection', {
        get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10, saveData: false })
    });

    // 9. Hardware concurrency / deviceMemory
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // 10. Platform
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

    // 11. Notification override
    if (typeof Notification !== 'undefined') {
        Object.defineProperty(Notification, 'permission', { get: () => 'default' });
    }
}
"""


async def _stealth_page(page: Page) -> None:
    """Apply comprehensive stealth patches to the page."""
    await page.add_init_script(STEALTH_JS)


class ShopeeScraper(IReviewScraper):
    """
    Scrapes Shopee reviews via their internal JSON API.
    Falls back to Playwright if the API approach fails.
    """

    async def scrape_reviews(self, url: str, max_reviews: int) -> list[Review]:
        if not self.check_robots_txt(url):
            logger.warning("Skipping Shopee scrape — blocked by robots.txt")
            return []

        shop_id, item_id = self._extract_ids(url)
        if not shop_id or not item_id:
            logger.warning("Could not extract shop_id/item_id from Shopee URL: %s", url)
            return await self._fallback_playwright(url, max_reviews)

        reviews = await self._scrape_via_api(shop_id, item_id, max_reviews)
        if not reviews:
            reviews = await self._fallback_playwright(url, max_reviews)

        return reviews[:max_reviews]

    def _extract_ids(self, url: str) -> tuple[str | None, str | None]:
        """Extract shop_id and item_id from a Shopee URL like /product/shop_id/item_id."""
        match = re.search(r'\.(\d+)\.(\d+)', url)
        if match:
            return match.group(1), match.group(2)
        match = re.search(r'i\.(\d+)\.(\d+)', url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    async def _scrape_via_api(self, shop_id: str, item_id: str, max_reviews: int) -> list[Review]:
        """Attempt to fetch reviews via Shopee's internal ratings API."""
        reviews: list[Review] = []
        offset = 0
        limit = 50

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": f"https://shopee.vn/product/{shop_id}/{item_id}",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        }

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            while len(reviews) < max_reviews:
                await rate_limiter.wait()

                api_url = (
                    f"https://shopee.vn/api/v2/item/get_ratings"
                    f"?itemid={item_id}&shopid={shop_id}"
                    f"&offset={offset}&limit={limit}&type=0"
                )

                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code != 200:
                        logger.warning("Shopee API returned %d", resp.status_code)
                        break

                    data = resp.json()
                    ratings = data.get("data", {}).get("ratings", [])
                    if not ratings:
                        break

                    for r in ratings:
                        comment = r.get("comment", "")
                        if comment:
                            reviews.append(Review(
                                text=sanitize_text(comment),
                                rating=float(r.get("rating_star", 3)),
                                date=str(r.get("ctime", "")),
                            ))

                    offset += limit
                except Exception as e:
                    logger.warning("Shopee API error: %s", e)
                    break

        return reviews

    def _parse_reviews(self, html: str) -> list[Review]:
        """Parse review data from Shopee rendered HTML.

        Shopee review structure (from actual HTML inspection):
          - Review container: div.q2b7Oq[data-cmtid]
          - Review text:      div.YNedDV
          - Rating stars:     count svg.icon-rating-solid inside div.rGdC5O
          - Date:             div.XYk98l
          - Parent list:      div.product-ratings__list > div.shopee-product-comment-list
        """
        soup = BeautifulSoup(html, "lxml")
        reviews: list[Review] = []

        # Primary selector: each review is a div with data-cmtid attribute
        review_els = soup.select("div.q2b7Oq[data-cmtid]")
        if not review_els:
            # Fallback: try the comment list container
            review_els = soup.select(".shopee-product-comment-list > div[data-cmtid]")
        logger.debug("Found %d elements with div.q2b7Oq[data-cmtid]", len(review_els))

        for el in review_els:
            try:
                # Review text — main review body is in div.YNedDV
                text_el = el.select_one("div.YNedDV")
                text = sanitize_text(text_el.get_text(strip=True)) if text_el else ""

                # Rating — count filled star SVGs (svg.icon-rating-solid)
                rating_container = el.select_one("div.rGdC5O")
                if rating_container:
                    stars = rating_container.select("svg.icon-rating-solid")
                    rating = float(len(stars)) if stars else 3.0
                else:
                    rating = 3.0

                # Date — e.g. "2024-09-30 22:03"
                date_el = el.select_one("div.XYk98l")
                date = date_el.get_text(strip=True) if date_el else ""

                if text:
                    reviews.append(Review(text=text, rating=rating, date=date))
            except Exception as e:
                logger.debug("Failed to parse Shopee review: %s", e)
                continue

        return reviews

    async def _fallback_playwright(self, url: str, max_reviews: int) -> list[Review]:
        """Fallback: use Playwright with comprehensive anti-detection to scrape reviews.

        Strategy:
          1. Block Shopee's anti-crawler scripts via route interception.
          2. Intercept XHR responses to capture ratings API JSON directly.
          3. Pre-warm session by visiting Shopee homepage first.
          4. Navigate to the product and wait for SPA to render.
          5. Parse intercepted API data first; fall back to HTML parsing.
        """
        reviews: list[Review] = []
        intercepted_ratings: list[dict] = []  # captured from network

        async def _handle_route(route: Route) -> None:
            """Block anticrawler / antifraud scripts to prevent detection."""
            req_url = route.request.url
            if any(kw in req_url for kw in ("anticrawler", "antifraud", "captcha")):
                logger.debug("Blocked anticrawler script: %s", req_url[:120])
                await route.abort()
            else:
                await route.continue_()

        async def _on_response(response) -> None:
            """Intercept XHR responses containing review/rating data."""
            req_url = response.url
            if "get_ratings" in req_url or "item_rating" in req_url:
                try:
                    body = await response.json()
                    intercepted_ratings.append(body)
                    logger.info("Intercepted ratings API response from %s", req_url[:120])
                except Exception:
                    pass

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-background-networking",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--window-size=1920,1080",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
                    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )
            page = await context.new_page()
            await _stealth_page(page)

            # Set up route interception to block anti-crawler scripts
            await page.route("**/*anticrawler*", _handle_route)
            await page.route("**/*antifraud*", _handle_route)
            await page.route("**/*captcha*", _handle_route)

            # Listen for responses containing review data
            page.on("response", _on_response)

            try:
                # --- Pre-warm: visit Shopee homepage to get cookies/session ---
                logger.info("Pre-warming Shopee session via homepage...")
                await page.goto("https://shopee.vn", wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(random.randint(2000, 3000))

                # --- Navigate to the actual product page ---
                logger.info("Navigating to Shopee product page: %s", url)
                await page.goto(url, wait_until="load", timeout=30000)

                # Wait for the SPA to render product content
                # Try waiting for common product page selectors
                product_rendered = False
                for selector in [
                    "div[data-cmtid]",                        # review element
                    ".product-ratings",                        # ratings section
                    ".shopee-product-comment-list",            # comment list
                    "div.q2b7Oq",                             # review container class
                    "div.flex-auto",                           # product detail area
                    "section.product-briefing",                # product briefing
                    ".page-product",                           # product page marker
                ]:
                    try:
                        await page.wait_for_selector(selector, timeout=8000)
                        logger.info("SPA rendered — found selector: %s", selector)
                        product_rendered = True
                        break
                    except Exception:
                        continue

                if not product_rendered:
                    logger.warning("SPA did not render product content; waiting longer...")
                    await page.wait_for_timeout(5000)

                # Check page title
                title = await page.title()
                logger.info("Shopee page title: '%s'", title)

                # Scroll progressively to trigger lazy-loaded content (reviews)
                logger.info("Scrolling through page to trigger review loading...")
                page_height = await page.evaluate("document.body.scrollHeight")
                scroll_pos = 0
                while scroll_pos < page_height:
                    scroll_pos += 400
                    await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                    await page.wait_for_timeout(random.randint(200, 400))
                    new_height = await page.evaluate("document.body.scrollHeight")
                    if new_height > page_height:
                        page_height = new_height

                # Wait a bit for any final network requests (review data)
                await page.wait_for_timeout(3000)

                # Try scrolling to the reviews section specifically
                await page.evaluate("""
                    const el = document.querySelector('.product-ratings__list')
                        || document.querySelector('.shopee-product-comment-list')
                        || document.querySelector('div[data-cmtid]')
                        || document.querySelector('.product-ratings');
                    if (el) el.scrollIntoView({ block: 'center' });
                """)
                await page.wait_for_timeout(2000)

                # --- Strategy 1: Parse reviews from intercepted API data ---
                for payload in intercepted_ratings:
                    try:
                        ratings = payload.get("data", {}).get("ratings", [])
                        for r in ratings:
                            comment = r.get("comment", "")
                            if comment:
                                reviews.append(Review(
                                    text=sanitize_text(comment),
                                    rating=float(r.get("rating_star", 3)),
                                    date=str(r.get("ctime", "")),
                                ))
                    except Exception as e:
                        logger.debug("Failed to parse intercepted rating: %s", e)

                if reviews:
                    logger.info("Got %d reviews from intercepted API responses", len(reviews))
                else:
                    # --- Strategy 2: Parse reviews from rendered HTML ---
                    # Debug: check what exists in the DOM
                    debug_info = await page.evaluate("""() => {
                        return {
                            cmtItems: document.querySelectorAll('div.q2b7Oq[data-cmtid]').length,
                            hasCommentList: !!document.querySelector('.shopee-product-comment-list'),
                            hasRatingsList: !!document.querySelector('.product-ratings__list'),
                            reviewTexts: document.querySelectorAll('div.YNedDV').length,
                            ratingStars: document.querySelectorAll('svg.icon-rating-solid').length,
                            hasPagination: !!document.querySelector('.shopee-page-controller'),
                            bodyLen: document.body.innerHTML.length,
                            divCount: document.querySelectorAll('div').length,
                            title: document.title,
                        };
                    }""")
                    logger.info("Shopee DOM debug: %s", debug_info)

                    content = await page.content()

                    # Save debug HTML
                    try:
                        with open("shopee_debug.html", "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info("Saved debug HTML (%d chars) to shopee_debug.html", len(content))
                    except Exception:
                        pass

                    reviews = self._parse_reviews(content)
                    logger.info("Found %d reviews from HTML parsing", len(reviews))

                # Pagination (only when HTML parsing found reviews)
                if reviews and len(reviews) < max_reviews:
                    await self._load_more_reviews(page, reviews, max_reviews)

            except Exception as e:
                logger.error("Shopee Playwright fallback error: %s", e)
            finally:
                await browser.close()

        return reviews

    async def _load_more_reviews(self, page: Page, reviews: list[Review], max_reviews: int) -> None:
        """Try to load more reviews by clicking the next page button."""
        for attempt in range(5):
            if len(reviews) >= max_reviews:
                break

            try:
                # Shopee pagination: button.shopee-icon-button--right is the next arrow
                next_btn = page.locator("button.shopee-icon-button--right")
                if await next_btn.count() == 0:
                    break

                # Check if button is disabled (last page)
                is_disabled = await next_btn.is_disabled()
                if is_disabled:
                    break

                await next_btn.click()
                await page.wait_for_timeout(random.randint(2000, 3000))

                content = await page.content()
                new_reviews = self._parse_reviews(content)
                if not new_reviews:
                    break

                reviews.extend(new_reviews)
                logger.info("Loaded %d total reviews after pagination click %d",
                            len(reviews), attempt + 1)
            except Exception as e:
                logger.debug("Shopee pagination attempt %d failed: %s", attempt + 1, e)
                break
