import logging
from dataclasses import dataclass
from typing import Optional

import requests

from competitor_price_monitor.models import DefaultsConfig, SiteConfig

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    html: str
    final_url: str
    renderer: str


class PageFetcher:
    def __init__(self, defaults: DefaultsConfig):
        self.defaults = defaults
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": defaults.user_agent})
        self._playwright = None
        self._browser = None

    def fetch_http(self, url: str, site: SiteConfig) -> FetchResult:
        headers = {"User-Agent": self.defaults.user_agent}
        headers.update(site.headers)
        response = self.session.get(url, headers=headers, timeout=site.timeout_sec)
        response.raise_for_status()
        logger.debug("Fetched %s with requests, final URL: %s", url, response.url)
        return FetchResult(html=response.text, final_url=response.url, renderer="http")

    def fetch_playwright(self, url: str, site: SiteConfig) -> FetchResult:
        sync_playwright = self._get_sync_playwright()
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)

        page = self._browser.new_page(user_agent=self.defaults.user_agent)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=site.playwright_timeout_sec * 1000)
            if site.wait_for:
                page.wait_for_selector(site.wait_for, timeout=site.playwright_timeout_sec * 1000)
            else:
                page.wait_for_load_state("networkidle", timeout=site.playwright_timeout_sec * 1000)
            html = page.content()
            final_url = page.url
            logger.debug("Fetched %s with Playwright, final URL: %s", url, final_url)
            return FetchResult(html=html, final_url=final_url, renderer="playwright")
        finally:
            page.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None

        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        self.session.close()

    def _get_sync_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright is not installed. Install dependencies from requirements.txt."
            ) from error

        return sync_playwright
