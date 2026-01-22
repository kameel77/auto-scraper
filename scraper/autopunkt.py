import re
import logging
import asyncio
import random
import time
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Browser
from .base import BaseScraper
from .offer_parser import parse_offer as legacy_parse_offer

logger = logging.getLogger(__name__)

class AutopunktScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="autopunkt", base_url="https://autopunkt.pl")
        self.list_url = "https://autopunkt.pl/znajdz-auto"

    async def collect_urls(self, max_scroll_rounds=60, scroll_pause=1.0, headless=True) -> list[str]:
        urls = set()
        self.logger.info(f"Rozpoczynam zbieranie URL-i z: {self.list_url}")
        
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=headless)
            page: Page = await browser.new_page()
            
            try:
                await page.set_viewport_size({"width": 1920, "height": 1080})
                self.logger.info("Ładowanie strony...")
                await page.goto(self.list_url, wait_until="networkidle", timeout=120_000)
                
                await self._handle_cookie_consent(page)
                urls = await self._scroll_and_collect(page, max_scroll_rounds, scroll_pause)
                
            except Exception as e:
                self.logger.error(f"Błąd podczas zbierania URL-i: {e}")
                raise
            finally:
                await browser.close()
        
        self.logger.info(f"Zebrano {len(urls)} unikalnych URL-i")
        return sorted(list(urls))

    async def _handle_cookie_consent(self, page: Page) -> None:
        consent_texts = ["Akceptuj", "Zgadzam się", "Accept", "OK", "Zgoda"]
        for txt in consent_texts:
            try:
                btn = page.get_by_role("button", name=re.compile(txt, re.I))
                if await btn.count() > 0:
                    await btn.first.click(timeout=2000)
                    self.logger.info(f"Kliknięto przycisk consent: {txt}")
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

    async def _scroll_and_collect(self, page: Page, max_rounds: int, scroll_pause: float) -> set[str]:
        urls = set()
        last_count = 0
        no_change_count = 0
        
        for round_num in range(max_rounds):
            hrefs = await page.eval_on_selector_all(
                "a[href*='/samochod/']",
                "els => els.map(e => e.href)"
            )
            
            for h in hrefs:
                if h and "/samochod/" in h:
                    clean_url = h.split("#", 1)[0].rstrip("/")
                    urls.add(clean_url)
            
            current_count = len(urls)
            self.logger.info(f"Runda {round_num + 1}/{max_rounds}: zebrano {current_count} URL-i")
            
            clicked = await self._try_load_more_button(page, scroll_pause)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(int(scroll_pause * 1000))
            
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 3 and not clicked:
                    self.logger.info("Brak nowych URL-i przez 3 rundy - kończę zbieranie")
                    break
            else:
                no_change_count = 0
            
            last_count = current_count
        
        return urls

    async def _try_load_more_button(self, page: Page, scroll_pause: float) -> bool:
        load_more_patterns = ["Pokaż więcej", "Załaduj więcej", "Wczytaj więcej", "Load more", "Zobacz więcej"]
        for pattern in load_more_patterns:
            try:
                btn = page.get_by_role("button", name=re.compile(pattern, re.I))
                if await btn.count() > 0:
                    await btn.first.click(timeout=2000)
                    self.logger.info(f"Kliknięto przycisk: {pattern}")
                    await page.wait_for_timeout(int(scroll_pause * 1000))
                    return True
            except Exception:
                continue
        return False

    def parse_offer(self, url: str) -> dict:
        # Reuse old offer parser logic for now
        return legacy_parse_offer(url)
