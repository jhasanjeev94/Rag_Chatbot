"""
Scraper module for the Document Ingestion Pipeline.

Fetches raw HTML from Groww corpus URLs with:
- User-Agent spoofing to avoid bot detection
- Retry logic (3x with exponential backoff)
- Disk caching to data/raw/<url_slug>.html
- Optional Playwright fallback for JS-rendered pages
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

from src.config import CORPUS_URLS

logger = logging.getLogger(__name__)

# --- Constants ---

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RAW_DATA_DIR = _PROJECT_ROOT / "data" / "raw"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds; retry delays: 2s, 4s, 8s
_REQUEST_TIMEOUT = 30  # seconds


# --- Exceptions ---

class ScrapingError(Exception):
    """Raised when a URL cannot be fetched after all retries."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to scrape {url}: {reason}")


# --- Helper Functions ---

def _url_to_slug(url: str) -> str:
    """Convert a URL to a filesystem-safe slug for caching.

    Example:
        'https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth'
        -> 'hdfc-large-cap-fund-direct-growth'
    """
    path = urlparse(url).path.strip("/")
    # Use the last path segment as the slug
    slug = path.split("/")[-1] if "/" in path else path
    # Fallback to hash if slug is empty
    if not slug:
        slug = hashlib.md5(url.encode()).hexdigest()[:16]
    return slug


def _get_cache_path(url: str) -> Path:
    """Return the cache file path for a given URL."""
    slug = _url_to_slug(url)
    return _RAW_DATA_DIR / f"{slug}.html"


# --- Core Scraping ---

def _fetch_with_requests(url: str) -> str:
    """Fetch HTML using the requests library with retry and backoff.

    Args:
        url: The URL to fetch.

    Returns:
        Raw HTML content as a string.

    Raises:
        ScrapingError: If all retry attempts fail.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    last_exception = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                "Fetching %s (attempt %d/%d) via requests",
                url, attempt, _MAX_RETRIES,
            )
            response = requests.get(
                url, headers=headers, timeout=_REQUEST_TIMEOUT
            )
            response.raise_for_status()

            html = response.text

            # Sanity check: Groww pages should have substantial content.
            # A very short response likely means we got a bot-block page.
            if len(html) < 1000:
                logger.warning(
                    "Response for %s is suspiciously short (%d chars), "
                    "may be a bot-block page.",
                    url, len(html),
                )

            return html

        except requests.exceptions.HTTPError as e:
            last_exception = e
            logger.warning(
                "HTTP error for %s on attempt %d: %s",
                url, attempt, e,
            )
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            logger.warning(
                "Connection error for %s on attempt %d: %s",
                url, attempt, e,
            )
        except requests.exceptions.Timeout as e:
            last_exception = e
            logger.warning(
                "Timeout for %s on attempt %d: %s",
                url, attempt, e,
            )
        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.warning(
                "Request error for %s on attempt %d: %s",
                url, attempt, e,
            )

        # Exponential backoff before next retry
        if attempt < _MAX_RETRIES:
            delay = _BACKOFF_BASE ** attempt
            logger.info("Retrying in %ds...", delay)
            time.sleep(delay)

    raise ScrapingError(url, str(last_exception))


def _fetch_with_playwright(url: str) -> str:
    """Fetch HTML using Playwright for JS-rendered pages.

    Falls back to this method when requests returns incomplete content.

    Args:
        url: The URL to fetch.

    Returns:
        Fully rendered HTML content as a string.

    Raises:
        ScrapingError: If Playwright is not installed or rendering fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ScrapingError(
            url,
            "Playwright is not installed. Install it with: "
            "pip install playwright && python -m playwright install chromium",
        )

    logger.info("Fetching %s via Playwright (headless browser)...", url)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()

            page.goto(url, wait_until="networkidle", timeout=60000)
            # Wait a bit for any lazy-loaded content
            page.wait_for_timeout(3000)

            html = page.content()
            browser.close()

            return html

    except Exception as e:
        raise ScrapingError(url, f"Playwright rendering failed: {e}")


# --- Public API ---

def scrape_url(url: str, use_cache: bool = True, force_playwright: bool = False) -> str:
    """Fetch raw HTML from a corpus URL.

    - Uses requests with User-Agent header by default
    - Retries 3x with exponential backoff
    - Caches raw HTML to data/raw/<url_slug>.html
    - Falls back to Playwright if response looks incomplete
    - Raises ScrapingError on failure

    Args:
        url: The URL to scrape.
        use_cache: If True, return cached HTML if it exists on disk.
        force_playwright: If True, skip requests and go straight to Playwright.

    Returns:
        Raw HTML content as a string.

    Raises:
        ScrapingError: If the URL cannot be fetched after all attempts.
    """
    cache_path = _get_cache_path(url)

    # Return cached version if available
    if use_cache and cache_path.exists():
        logger.info("Using cached HTML for %s from %s", url, cache_path)
        return cache_path.read_text(encoding="utf-8")

    # Fetch HTML
    if force_playwright:
        html = _fetch_with_playwright(url)
    else:
        html = _fetch_with_requests(url)

        # If response is suspiciously short, try Playwright as fallback
        if len(html) < 1000:
            logger.warning(
                "requests returned only %d chars for %s, "
                "attempting Playwright fallback...",
                len(html), url,
            )
            try:
                html = _fetch_with_playwright(url)
            except ScrapingError as e:
                logger.warning(
                    "Playwright fallback failed: %s. "
                    "Using the short requests response instead.",
                    e.reason,
                )
                # Keep the requests HTML — it might still be partially useful

    # Cache to disk
    _RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    logger.info("Cached HTML for %s to %s (%d chars)", url, cache_path, len(html))

    return html


def scrape_all(
    urls: Optional[List[str]] = None,
    use_cache: bool = True,
    force_playwright: bool = False,
) -> Dict[str, str]:
    """Scrape all corpus URLs and return a mapping of URL -> HTML.

    Args:
        urls: List of URLs to scrape. Defaults to CORPUS_URLS from config.
        use_cache: If True, use cached HTML when available.
        force_playwright: If True, use Playwright for all URLs.

    Returns:
        Dict mapping each URL to its raw HTML content.
        URLs that failed to scrape are logged but excluded from results.
    """
    if urls is None:
        urls = CORPUS_URLS

    results: Dict[str, str] = {}

    for i, url in enumerate(urls, 1):
        logger.info("--- Scraping URL %d/%d: %s ---", i, len(urls), url)
        try:
            html = scrape_url(
                url, use_cache=use_cache, force_playwright=force_playwright
            )
            results[url] = html
            logger.info(
                "✓ Scraped %s (%d chars)", url, len(html),
            )
        except ScrapingError as e:
            logger.error("✗ Failed to scrape %s: %s", url, e.reason)

    logger.info(
        "Scraping complete: %d/%d URLs succeeded.", len(results), len(urls),
    )

    return results


# --- CLI Entry Point ---

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting scraper for %d corpus URLs...", len(CORPUS_URLS))
    results = scrape_all()
    for url, html in results.items():
        print(f"  {url} -> {len(html)} chars")
