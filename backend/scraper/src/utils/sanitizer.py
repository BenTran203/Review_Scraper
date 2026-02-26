"""PII sanitization for scraped review data.

Strips reviewer names, profile URLs, emails, phone numbers, and other
personally identifiable information. Only the review text, rating, and
date are kept.
"""

from __future__ import annotations

import re


# Patterns to redact from review text
_EMAIL_RE = re.compile(r'\b[\w.-]+@[\w.-]+\.\w+\b')
_PHONE_RE = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')
_URL_RE = re.compile(r'https?://\S+')
_SOCIAL_RE = re.compile(r'@[\w.]+', re.UNICODE)


def sanitize_text(text: str) -> str:
    """
    Remove PII from review text.

    - Strips emails, phone numbers, URLs, and social media handles.
    - Collapses excessive whitespace.
    - Truncates to 1000 characters to limit downstream token usage.
    """
    if not text:
        return ""

    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[phone]", text)
    text = _URL_RE.sub("[link]", text)
    text = _SOCIAL_RE.sub("[user]", text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate
    if len(text) > 1000:
        text = text[:997] + "..."

    return text
