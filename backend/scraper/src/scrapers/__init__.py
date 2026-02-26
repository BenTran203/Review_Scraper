from .base import IReviewScraper, Review
from .amazon import AmazonScraper
from .shopee import ShopeeScraper
from .ebay import EbayScraper
from .lazada import LazadaScraper
from .tiki import TikiScraper

PLATFORM_SCRAPERS: dict[str, type[IReviewScraper]] = {
    "amazon": AmazonScraper,
    "shopee": ShopeeScraper,
    "ebay": EbayScraper,
    "lazada": LazadaScraper,
    "tiki": TikiScraper,
}

__all__ = [
    "IReviewScraper",
    "Review",
    "PLATFORM_SCRAPERS",
    "AmazonScraper",
    "ShopeeScraper",
    "EbayScraper",
    "LazadaScraper",
    "TikiScraper",
]
