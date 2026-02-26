"""
RabbitMQ consumer worker — the main entry point for the scraper service.

Listens on the scrape_jobs queue, dispatches to the appropriate platform
scraper (custom or third-party adapter), applies weighted sampling, and
publishes results back to the scrape_results queue.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import time

import pika

from .config import config
from .scrapers import PLATFORM_SCRAPERS, IReviewScraper
from .scrapers.adapters.scraperapi import ScraperAPIScraper
from .scrapers.adapters.oxylabs import OxylabsScraper
from .utils.redis_client import RedisClient
from .utils.sampler import sample_reviews

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("scraper.worker")


def get_scraper(platform: str) -> IReviewScraper:
    """
    Return the appropriate scraper based on SCRAPER_ADAPTER config.

    - "custom" (default): uses platform-specific Playwright/BS4 scrapers
    - "scraperapi": routes all platforms through ScraperAPI
    - "oxylabs": routes all platforms through Oxylabs
    """
    adapter = config.SCRAPER_ADAPTER.lower()

    if adapter == "scraperapi":
        return ScraperAPIScraper(api_key=config.SCRAPERAPI_KEY)
    elif adapter == "oxylabs":
        return OxylabsScraper(username=config.OXYLABS_USER, password=config.OXYLABS_PASS)
    else:
        scraper_cls = PLATFORM_SCRAPERS.get(platform)
        if not scraper_cls:
            raise ValueError(f"Unsupported platform: {platform}")
        return scraper_cls()


async def handle_job(body: bytes, redis_client: RedisClient, channel, method) -> None:
    """Process a single scrape job."""
    try:
        job = json.loads(body)
        token = job["token"]
        url = job["url"]
        platform = job["platform"]

        logger.info("Processing scrape job: token=%s platform=%s url=%s", token, platform, url)

        # Update status to scraping
        redis_client.update_status(token, "scraping")

        # Get scraper
        scraper = get_scraper(platform)

        # Scrape reviews (fetch more than needed for sampling)
        fetch_count = int(config.MAX_REVIEWS * 1.5)  # Over-fetch for sampling
        raw_reviews = await scraper.scrape_reviews(url, fetch_count)

        logger.info("Scraped %d raw reviews for token=%s", len(raw_reviews), token)

        # Apply weighted sampling
        sampled = sample_reviews(
            raw_reviews,
            max_total=config.MAX_REVIEWS,
            positive_ratio=config.POSITIVE_RATIO,
            negative_ratio=config.NEGATIVE_RATIO,
        )

        logger.info("Sampled %d reviews (from %d) for token=%s", len(sampled), len(raw_reviews), token)

        # Store reviews in Redis
        redis_client.store_reviews(token, [r.to_dict() for r in sampled])

        # Publish result to scrape_results queue
        result = {
            "token": token,
            "reviews": [r.to_dict() for r in sampled],
            "error": "",
        }
        channel.basic_publish(
            exchange="",
            routing_key=config.SCRAPE_RESULTS_QUEUE,
            body=json.dumps(result),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        logger.info("Published scrape result for token=%s (%d reviews)", token, len(sampled))

    except Exception as e:
        logger.error("Scrape job failed: %s", e, exc_info=True)
        try:
            token = json.loads(body).get("token", "unknown")
            error_result = {
                "token": token,
                "reviews": [],
                "error": str(e),
            }
            channel.basic_publish(
                exchange="",
                routing_key=config.SCRAPE_RESULTS_QUEUE,
                body=json.dumps(error_result),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        except Exception:
            logger.error("Failed to publish error result", exc_info=True)


def main() -> None:
    """Start the RabbitMQ consumer loop."""
    logger.info("Starting scraper worker...")
    logger.info("Adapter: %s | Max reviews: %d | Ratio: %.0f%% pos / %.0f%% neg",
                config.SCRAPER_ADAPTER, config.MAX_REVIEWS,
                config.POSITIVE_RATIO * 100, config.NEGATIVE_RATIO * 100)

    redis_client = RedisClient(config.REDIS_URL)
    if not redis_client.ping():
        logger.error("Cannot connect to Redis at %s", config.REDIS_URL)
        sys.exit(1)
    logger.info("Connected to Redis")

    # Connect to RabbitMQ with retry
    connection = None
    for attempt in range(1, 11):
        try:
            connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
            break
        except pika.exceptions.AMQPConnectionError:
            logger.warning("RabbitMQ not ready, retrying in %ds... (attempt %d/10)", attempt, attempt)
            time.sleep(attempt)  # linear back-off: 1s, 2s, 3s, ...

    if connection is None:
        logger.error("Cannot connect to RabbitMQ at %s after 10 attempts", config.RABBITMQ_URL)
        sys.exit(1)

    channel = connection.channel()
    channel.queue_declare(queue=config.SCRAPE_JOBS_QUEUE, durable=True)
    channel.queue_declare(queue=config.SCRAPE_RESULTS_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    logger.info("Connected to RabbitMQ")

    loop = asyncio.new_event_loop()

    def on_message(ch, method, properties, body):
        """Callback for each incoming scrape job."""
        try:
            loop.run_until_complete(handle_job(body, redis_client, channel, method))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("Message processing failed: %s", e, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=config.SCRAPE_JOBS_QUEUE, on_message_callback=on_message)

    # Graceful shutdown
    def shutdown(sig, frame):
        logger.info("Shutting down worker...")
        channel.stop_consuming()
        connection.close()
        loop.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Worker ready — consuming from '%s'", config.SCRAPE_JOBS_QUEUE)
    channel.start_consuming()


if __name__ == "__main__":
    main()
