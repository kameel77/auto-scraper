import re
import json
import time
import random
import logging
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)

class FindcarScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="findcar", base_url="https://findcar.pl")
        self.list_url = "https://findcar.pl/oferty-dealerow?priceType=offer&size={}&sort=createdAt,desc&page={}"
        self.detail_api = "https://findcar.pl/api/listings/{}"
        self.session = self._make_session()

    def _make_session(self):
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "DNT": "1"
        })
        return s

    def _safe_int(self, x):
        if x is None: return None
        if isinstance(x, (int, float)): return int(x)
        digits = re.findall(r"\d+", str(x).replace("\xa0", "").replace(" ", ""))
        return int("".join(digits)) if digits else None

    def _specs_to_dict(self, spec_list):
        return {it.get("label"): it.get("value") for it in (spec_list or [])}

    def _equipment_to_dict(self, equipment_list):
        out = {"Audio": [], "Bezpieczeństwo": [], "Komfort": [], "Inne": []}
        for sec in equipment_list or []:
            name = sec.get("sectionName", "")
            items = sec.get("items") or []
            if "Audio" in name: out["Audio"].extend(items)
            elif "Bezpieczeństwo" in name: out["Bezpieczeństwo"].extend(items)
            elif "Komfort" in name or "dodatki" in name.lower(): out["Komfort"].extend(items)
            else: out["Inne"].extend(items)
        return out

    def detail_to_row(self, detail, listing_id: str):
        card = detail.get("cardInfo") or {}
        pricing = (card.get("pricing") or {}).get("offer") or {}
        omnibus = pricing.get("omnibus") or {}
        specs = self._specs_to_dict(detail.get("specifications"))
        eq = self._equipment_to_dict(detail.get("equipment"))
        media = detail.get("media") or []
        image_urls = [m.get("url") for m in media if m.get("type") == "image" and m.get("url")]
        dealer = detail.get("dealer") or {}
        addr = dealer.get("address") or {}

        price_pln100 = pricing.get("offerPricePln100")
        price_pln = (price_pln100 / 100) if isinstance(price_pln100, int) else None

        # Prepare image list: primary first, then others
        other_images = [img for img in image_urls if img != card.get("primaryImage")]
        all_ordered_images = []
        if card.get("primaryImage"):
            all_ordered_images.append(card.get("primaryImage"))
        all_ordered_images.extend(other_images)

        return {
            "listing_id": listing_id,
            "numer_oferty": listing_id,
            "url": f"{self.base_url}/listings/{listing_id}",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "marka": specs.get("Marka") or (card.get("make") or {}).get("text"),
            "model": specs.get("Model") or (card.get("model") or {}).get("text"),
            "wersja": specs.get("Wersja") or card.get("version"),
            "vin": specs.get("VIN"),
            "cena_brutto_pln": price_pln,
            "price_display": pricing.get("displayAmount"),
            "omnibus_lowest_30d_pln": (omnibus.get("lowestPricePln100") / 100) if isinstance(omnibus.get("lowestPricePln100"), int) else None,
            "omnibus_text": omnibus.get("displayText"),
            "rocznik": self._safe_int(specs.get("Rok produkcji") or card.get("productionYear")),
            "przebieg_km": self._safe_int(specs.get("Przebieg") or card.get("mileageKm")),
            "typ_silnika": specs.get("Silnik / rodzaj paliwa") or (card.get("fuelType") or {}).get("text"),
            "skrzynia_biegow": specs.get("Skrzynia biegów") or (card.get("transmission") or {}).get("text"),
            "moc_km": self._safe_int(specs.get("Moc") or card.get("enginePowerHp")),
            "registration_number": specs.get("Numer rejestracyjny"),
            "pierwsza_rejestracja": specs.get("Data pierwszej rejestracji"),
            "pojemnosc_cm3": self._safe_int(specs.get("Pojemność silnika")),
            "naped": specs.get("Napęd"),
            "typ_nadwozia": specs.get("Rodzaj nadwozia"),
            "ilosc_drzwi": self._safe_int(specs.get("Liczba drzwi")),
            "seats": self._safe_int(specs.get("Liczba miejsc")),
            "kolor": specs.get("Kolor"),
            "paint_type": specs.get("Rodzaj lakieru"),
            "dealer_name": dealer.get("name"),
            "dealer_address_line_1": addr.get("line1"),
            "dealer_address_line_2": addr.get("line2"),
            "dealer_address_line_3": addr.get("line3"),
            "dealer_google_rating": dealer.get("googleRating"),
            "dealer_review_count": self._safe_int(dealer.get("reviewCount")),
            "dealer_google_link": dealer.get("googleLink"),
            "contact_phone": detail.get("contactPhone"),
            "primary_image_url": card.get("primaryImage"),
            "image_count": len(all_ordered_images),
            "zdjecia": " | ".join(all_ordered_images),
            "equipment_audio_multimedia": "|".join(eq["Audio"]),
            "equipment_safety": "|".join(eq["Bezpieczeństwo"]),
            "equipment_comfort_extras": "|".join(eq["Komfort"]),
            "equipment_other": "|".join(eq["Inne"]),
            "additional_info_header": (detail.get("additionalInfo") or {}).get("header"),
            "additional_info_content": (detail.get("additionalInfo") or {}).get("content"),
            "specs_json": json.dumps(specs, ensure_ascii=False),
            "source": "findcar.pl"
        }

    async def collect_urls(self, max_pages=10, page_size=50, start_page=0, **kwargs) -> list[str]:
        all_ids = []
        
        # Warm up session by visiting home page
        try:
            self.logger.info("Rozgrzewanie sesji (visit home page)...")
            self.session.get(self.base_url, timeout=20)
            time.sleep(random.uniform(1.0, 2.5))
        except Exception as e:
            self.logger.warning(f"Problem z rozgrzewaniem sesji: {e}")

        for p_idx in range(start_page, start_page + max_pages):
            offset = p_idx * page_size
            self.logger.info(f"Pobieranie strony {p_idx} (Offset: {offset}, Size: {page_size})...")
            
            if p_idx > start_page:
                referer = self.list_url.format(page_size, offset - page_size)
            else:
                referer = f"{self.base_url}/"

            self.session.headers.update({
                "Referer": referer,
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            })

            target_url = self.list_url.format(page_size, offset)
            try:
                if p_idx > start_page:
                    time.sleep(random.uniform(1.5, 3.5))

                response = self.session.get(target_url, timeout=30)
                if response.status_code != 200:
                    self.logger.error(f"  ❌ Błąd HTTP {response.status_code} dla {target_url}")
                
                response.raise_for_status()

                # 1. New robust regex for ID extraction (handles slugs/intermediate chars)
                # Matches URLs like /oferty-dealerow/some-slug-012345678
                found_ids_url = re.findall(r'/oferty-dealerow/[^"\']*?-(\d{5,9})(?:\?|#|")', response.text)
                ids = set(found_ids_url)

                # 2. Fallback: Search for publicListingNumber in JSON-like structure
                json_ids = re.findall(r'"publicListingNumber"\s*:\s*"(\d+)"', response.text)
                if json_ids:
                    ids.update(json_ids)
                    self.logger.debug(f"  ℹ️ Użyto metody JSON fallback dla strony {p_idx}")

                if not ids:
                    self.logger.info(f"  ⚠️ Nie znaleziono ID na stronie {p_idx}. Status: {response.status_code}. Długość body: {len(response.text)}")
                    if len(response.text) < 1000:
                        self.logger.debug(f"  Snippet: {response.text[:500]}")
                    break

                result = sorted(list(ids))
                if result:
                    self.logger.debug(f"  (Debug: Znaleziono przykładowe ID: {result[:3]}...)")

                all_ids.extend(result)
                self.logger.info(f"  📌 Znaleziono {len(ids)} ofert na stronie.")
            except Exception as e:
                self.logger.error(f"Błąd strony {p_idx}: {e}")
                break
        
        return [f"{self.base_url}/listings/{lid}" for lid in all_ids]

    def parse_offer(self, url: str) -> dict:
        listing_id = url.split("/")[-1]
        try:
            data = self.session.get(self.detail_api.format(listing_id), timeout=30).json()
            return self.detail_to_row(data, listing_id)
        except Exception as e:
            self.logger.error(f"Błąd ID {listing_id}: {e}")
            raise
