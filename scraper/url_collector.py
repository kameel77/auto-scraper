"""
URL Collector - zbiera linki do ofert ze strony autopunkt.pl
"""
import re
import logging
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)


async def collect_offer_urls(
    list_url: str = "https://autopunkt.pl/znajdz-auto",
    max_scroll_rounds: int = 60,
    scroll_pause: float = 1.0,
    headless: bool = True
) -> list[str]:
    """
    Zbiera linki do ofert samochodów używając Playwright do scrollowania strony.
    
    Args:
        list_url: URL strony z listą ofert
        max_scroll_rounds: Maksymalna liczba rund scrollowania
        scroll_pause: Pauza (w sekundach) między scrollami
        headless: Czy przeglądarka ma działać w trybie headless
        
    Returns:
        Posortowana lista unikalnych URL-i do ofert
    """
    urls = set()
    
    logger.info(f"Rozpoczynam zbieranie URL-i z: {list_url}")
    
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        page: Page = await browser.new_page()
        
        try:
            # Konfiguracja strony
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Załaduj stronę
            logger.info("Ładowanie strony...")
            await page.goto(list_url, wait_until="networkidle", timeout=120_000)
            
            # Obsługa cookie consent
            await _handle_cookie_consent(page)
            
            # Scrollowanie i zbieranie linków
            urls = await _scroll_and_collect(page, max_scroll_rounds, scroll_pause, list_url)
            
        except Exception as e:
            logger.error(f"Błąd podczas zbierania URL-i: {e}")
            raise
        finally:
            await browser.close()
    
    logger.info(f"Zebrano {len(urls)} unikalnych URL-i")
    return sorted(urls)


async def _handle_cookie_consent(page: Page) -> None:
    """Próbuje zaakceptować cookie consent banner."""
    consent_texts = ["Akceptuj", "Zgadzam się", "Accept", "OK", "Zgoda"]
    
    for txt in consent_texts:
        try:
            btn = page.get_by_role("button", name=re.compile(txt, re.I))
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                logger.info(f"Kliknięto przycisk consent: {txt}")
                await page.wait_for_timeout(1000)
                break
        except Exception:
            continue


async def _scroll_and_collect(
    page: Page,
    max_rounds: int,
    scroll_pause: float,
    base_url: str
) -> set[str]:
    """Scrolluje stronę i zbiera linki do ofert."""
    urls = set()
    last_count = 0
    no_change_count = 0
    
    for round_num in range(max_rounds):
        # Zbierz wszystkie linki zawierające '/samochod/'
        hrefs = await page.eval_on_selector_all(
            "a[href*='/samochod/']",
            "els => els.map(e => e.href)"
        )
        
        # Normalizuj i dodaj do zbioru
        for h in hrefs:
            if h and "/samochod/" in h:
                # Usuń fragment (#hash)
                clean_url = h.split("#", 1)[0]
                # Usuń trailing slash dla spójności
                clean_url = clean_url.rstrip("/")
                urls.add(clean_url)
        
        current_count = len(urls)
        logger.info(f"Runda {round_num + 1}/{max_rounds}: zebrano {current_count} URL-i")
        
        # Próba kliknięcia "Pokaż więcej"
        clicked = await _try_load_more_button(page, scroll_pause)
        
        # Scroll na dół strony
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(int(scroll_pause * 1000))
        
        # Warunek stopu: brak nowych linków
        if current_count == last_count:
            no_change_count += 1
            if no_change_count >= 3 and not clicked:
                logger.info("Brak nowych URL-i przez 3 rundy - kończę zbieranie")
                break
        else:
            no_change_count = 0
        
        last_count = current_count
    
    return urls


async def _try_load_more_button(page: Page, scroll_pause: float) -> bool:
    """
    Próbuje znaleźć i kliknąć przycisk "Pokaż więcej" / "Load more".
    
    Returns:
        True jeśli udało się kliknąć, False w przeciwnym razie
    """
    load_more_patterns = [
        "Pokaż więcej",
        "Załaduj więcej",
        "Wczytaj więcej",
        "Load more",
        "Zobacz więcej"
    ]
    
    for pattern in load_more_patterns:
        try:
            btn = page.get_by_role("button", name=re.compile(pattern, re.I))
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                logger.info(f"Kliknięto przycisk: {pattern}")
                await page.wait_for_timeout(int(scroll_pause * 1000))
                return True
        except Exception:
            continue
    
    return False
