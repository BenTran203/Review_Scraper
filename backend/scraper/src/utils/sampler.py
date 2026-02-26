"""Weighted review sampling: ~60% positive (4-5 stars), ~40% negative (1-3 stars).

This ensures the AI gets a balanced dataset for generating meaningful
pros and cons without needing to scrape thousands of reviews.
"""

from __future__ import annotations

import random
from ..scrapers.base import Review


def sample_reviews(
    reviews: list[Review],
    max_total: int,
    positive_ratio: float = 0.6,
    negative_ratio: float = 0.4,
) -> list[Review]:
    """
    Sample reviews with a weighted distribution by rating.

    Args:
        reviews: All scraped reviews.
        max_total: Maximum number of reviews to return.
        positive_ratio: Target fraction of positive (4-5 star) reviews.
        negative_ratio: Target fraction of negative (1-3 star) reviews.

    Returns:
        A balanced subset of reviews.
    """
    if len(reviews) <= max_total:
        return reviews

    positive = [r for r in reviews if r.rating >= 4.0]
    negative = [r for r in reviews if r.rating < 4.0]

    target_positive = int(max_total * positive_ratio)
    target_negative = int(max_total * negative_ratio)

    # If one bucket doesn't have enough, give the surplus to the other
    if len(positive) < target_positive:
        sampled_positive = positive
        target_negative = max_total - len(sampled_positive)
    else:
        sampled_positive = random.sample(positive, target_positive)

    if len(negative) < target_negative:
        sampled_negative = negative
        # Fill remaining with more positives
        remaining = max_total - len(sampled_positive) - len(sampled_negative)
        extra_positive = [r for r in positive if r not in sampled_positive]
        sampled_positive.extend(extra_positive[:remaining])
    else:
        sampled_negative = random.sample(negative, target_negative)

    result = sampled_positive + sampled_negative
    random.shuffle(result)  # Mix so the AI doesn't see them grouped by rating
    return result[:max_total]
