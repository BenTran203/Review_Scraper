"""Scraper service configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load .env file if present (no error if missing — production uses real env vars)
load_dotenv()


class Config:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    # Which scraper implementation to use: "custom" | "scraperapi" | "oxylabs"
    SCRAPER_ADAPTER: str = os.getenv("SCRAPER_ADAPTER", "custom")

    # Third-party API keys (only needed if SCRAPER_ADAPTER != "custom")
    SCRAPERAPI_KEY: str = os.getenv("SCRAPERAPI_KEY", "")
    OXYLABS_USER: str = os.getenv("OXYLABS_USER", "")
    OXYLABS_PASS: str = os.getenv("OXYLABS_PASS", "")

    # Review sampling
    MAX_REVIEWS: int = int(os.getenv("MAX_REVIEWS", "200"))
    POSITIVE_RATIO: float = float(os.getenv("REVIEW_POSITIVE_RATIO", "0.6"))
    NEGATIVE_RATIO: float = float(os.getenv("REVIEW_NEGATIVE_RATIO", "0.4"))

    # Rate limiting (seconds between requests to the same domain)
    RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "1.5"))

    # Queue names (must match Go gateway constants)
    SCRAPE_JOBS_QUEUE: str = "scrape_jobs"
    SCRAPE_RESULTS_QUEUE: str = "scrape_results"


config = Config()
