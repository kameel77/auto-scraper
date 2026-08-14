import os
import re
import json
import logging
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

from .base import BaseScraper

load_dotenv()
logger = logging.getLogger(__name__)


def get_default_openrouter_key() -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        fallback_paths = [
            "/Users/kamiltonkowicz/.gemini/config/skills/voice_to_md/.env",
            os.path.expanduser("~/.openrouter_key"),
            os.path.expanduser("~/.config/openrouter/key")
        ]
        for p in fallback_paths:
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        for line in f:
                            if line.startswith("OPENROUTER_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break
                    if api_key:
                        break
                except Exception:
                    pass
    return api_key


class FiatPgdScraper(BaseScraper):
    """
    Scraper dla ofert samochodów dostawczych i ciężarowych z portalu Fiat PGD (fiat.pgd.pl).
    Wspiera zaawansowaną kategoryzację pełnego wyposażenia standardowego i dodatkowego przez LLM (OpenRouter).
    """

    DEFAULT_LIST_URL = "https://fiat.pgd.pl/p/dostepne-od-reki?75=ci%C4%99%C5%BCarowy"

    def __init__(self, base_url: str = "https://fiat.pgd.pl", use_llm: bool = True, llm_model: str = "google/gemini-3.5-flash-lite"):
        super().__init__(name="fiat_pgd", base_url=base_url)
        self.session = self._make_session()
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.openrouter_api_key = get_default_openrouter_key()

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1"
        })
        return s

    def _safe_int(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.findall(r"\d+", str(value).replace("\xa0", "").replace(" ", "").replace(",", ".").split(".")[0])
        return int("".join(digits)) if digits else None

    def _parse_capacity(self, value):
        if not value:
            return None
        cleaned = re.sub(r"cm\s*3?", "", str(value), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", "", cleaned)
        match = re.search(r"(\d+)", cleaned)
        return int(match.group(1)) if match else None

    def _parse_omnibus(self, text):
        if not text:
            return None
        match = re.search(r"(\d[\d\s]*\d)\s*(?:zł|PLN|netto|brutto)", text, re.IGNORECASE)
        if match:
            return int(re.sub(r"\s+", "", match.group(1)))
        return None

    async def collect_urls(self, limit: int | None = None, base_url: str | None = None, **kwargs) -> list[str]:
        """
        Zbiera adresy URL ofert samochodów, przechodząc przez paginację.
        """
        target_list_url = base_url or self.DEFAULT_LIST_URL
        self.logger.info(f"Rozpoczynam zbieranie URL-i z Fiat PGD: {target_list_url} (limit: {limit})")

        all_urls = []
        page = 1
        max_pages = kwargs.get("max_pages", 100)

        while page <= max_pages:
            delimiter = "&" if "?" in target_list_url else "?"
            page_url = f"{target_list_url}{delimiter}strona={page}" if page > 1 else target_list_url

            self.logger.info(f"Pobieranie strony {page}: {page_url}")
            try:
                resp = self.session.get(page_url, timeout=30)
                if resp.status_code == 404:
                    self.logger.info(f"Strona {page} zwróciła 404 - koniec paginacji.")
                    break
                resp.raise_for_status()
            except Exception as e:
                self.logger.error(f"Błąd podczas pobierania strony {page_url}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            found_urls = []

            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/samochod/" in href:
                    full_url = urljoin(self.base_url, href)
                    clean_url = full_url.split("#")[0].split("?")[0]
                    if clean_url not in found_urls and clean_url not in all_urls:
                        found_urls.append(clean_url)

            if not found_urls:
                self.logger.info(f"Brak nowych ofert na stronie {page} - koniec zbierania.")
                break

            self.logger.info(f"Strona {page}: znaleziono {len(found_urls)} ofert (łącznie dotychczas: {len(all_urls) + len(found_urls)})")
            all_urls.extend(found_urls)

            if limit and len(all_urls) >= limit:
                all_urls = all_urls[:limit]
                break

            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                break

            next_page_str = f"strona={page + 1}"
            has_next = any(next_page_str in a.get("href", "") for a in pagination.find_all("a", href=True))
            if not has_next and page > 1:
                break

            page += 1

        self.logger.info(f"Łącznie zebrano {len(all_urls)} unikalnych URL-i z Fiat PGD")
        return all_urls

    def _extract_all_raw_equipment(self, soup: BeautifulSoup) -> list[str]:
        """
        Wydobywa wszystkie surowe pozycje wyposażenia z sekcji górnej oraz z pełnego opisu
        (Wyposażenie standardowe + Wyposażenie dodatkowe / opcjonalne).
        """
        raw_items = []

        # 1. Górna sekcja Wyposażenie
        eq_h3 = soup.find(lambda e: e.name == "h3" and "wyposażenie" in e.text.lower())
        if eq_h3:
            curr = eq_h3.find_next_sibling()
            while curr and curr.name != "h3":
                if curr.name == "p":
                    items = [it.strip() for it in curr.text.replace("\n", " ").split(",") if it.strip()]
                    raw_items.extend([it for it in items if len(it) > 1 and it != ","])
                curr = curr.find_next_sibling()

        # 2. Wyposażenie standardowe i dodatkowe ze szczegółowego opisu
        soup_copy = BeautifulSoup(str(soup), "html.parser")
        for tag in soup_copy.find_all(["br", "p", "div", "li"]):
            tag.insert_after("\n")

        add_info_h3 = soup_copy.find(lambda e: e.name == "h3" and "dodatkowe informacje" in e.text.lower())
        if add_info_h3:
            full_text = add_info_h3.parent.get_text() if add_info_h3.parent else ""
            lines = [l.strip().lstrip("-•*").strip() for l in full_text.split("\n") if l.strip()]

            mode = None
            for l in lines:
                llow = l.lower()
                if "wyposażenie standardowe" in llow:
                    mode = "std"
                    continue
                elif "wyposażenie dodatkowe" in llow or "wyposażenie opcjonalne" in llow:
                    mode = "opt"
                    continue
                elif any(k in llow for k in [
                    "przed przyjazdem", "gwarancja producenta", "istnieje możliwość",
                    "cena auta", "najniższa cena", "auto zarejestrowane",
                    "promocyjne ubezpieczenie", "na miejscu możliwość"
                ]):
                    mode = None
                    continue

                if mode in ["std", "opt"] and len(l) > 2 and not l.startswith("_") and not l.startswith("http"):
                    raw_items.append(l)

        # Usunięcie duplikatów z zachowaniem kolejności
        unique_items = []
        seen = set()
        for it in raw_items:
            clean = re.sub(r"\s+", " ", it).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                unique_items.append(clean)

        return unique_items

    def _categorize_with_llm(self, raw_items: list[str]) -> dict:
        """
        Kategoryzuje pełną listę wyposażenia przy użyciu modelu LLM przez OpenRouter.
        Dokonuje inteligentnej dedukublikacji semantycznej oraz oczyszcza kody fabryczne.
        """
        if not raw_items or not self.openrouter_api_key:
            return self._categorize_fallback(raw_items)

        prompt = f"""Jesteś ekspertem motoryzacyjnym portalu Car-Scout.
Otrzymujesz surową listę wyposażenia samochodu dostawczego/ciężarowego z portalu dealera.
Lista zawiera powtórzenia (ogólne hasła ze skrótów oraz szczegółowe opisy z kodami wyposażenia standardowego i dodatkowego).

TWOJE ZADANIE:
1. DEDUPLIKACJA SEMANTYCZNA:
   - Usuń wszelkie powtórzenia tego samego elementu (np. "Podgrzewane lusterka zewnętrzne" vs "Boczne lusterka regulowane elektrycznie i podgrzewane" -> zachowaj TYLKO JEDNĄ, najdokładniejszą wersję).
   - Jeśli opcja dodatkowa ulepsza wyposażenie standardowe (np. "Klimatyzacja manualna" vs "Klimatyzacja automatyczna" lub "Tapicerka standardowa" vs "Tapicerka Lounge"), zachowaj FAKTYCZNIE zamontowaną wersję wyższą ("Klimatyzacja automatyczna", "Tapicerka Lounge").
2. OCZYSZCZENIE NAZW:
   - Usuń prefiksy kodów fabrycznych z początku linii (np. "041 - ", "025 - ", "03C - ", "132 - ", "077 ", "835 ", "C92 ", "1RB "), tak aby powstała estetyczna, czytelna nazwa dla klienta.
   - Zachowaj kluczowe parametry techniczne i użytkowe (np. "Alternator 180A", "Akumulator L5 95Ah", "Wzmocnione zawieszenie tylne z podwójnymi resorami", "Trwała przegroda z blachy bez szyby", "Zbiornik paliwa 90L", "Drzwi tylne otwierane pod kątem 270 stopni", "Półka pod sufitem").
3. PODZIAŁ NA DOKŁADNIE 4 KATEGORIE CAR-SCOUT:
   - "equipment_audio_multimedia": audio, radio, ekran dotykowy, Bluetooth, DAB, USB, Apple CarPlay, Android Auto, nawigacja GPS, kamera cofania, usługi łączności, moduł telematyczny SOS/Assistance, sterowanie z kierownicy.
   - "equipment_safety": poduszki powietrzne, pasy bezpieczeństwa, ABS, ESP/ESC, ASR, asystent bocznego wiatru, stabilizacja toru jazdy, asystent pasa ruchu, rozpoznawanie znaków, czujniki parkowania/cofania, czujnik deszczu i zmierzchu, TPMS (kontrola ciśnienia w oponach), światła do jazdy dziennej, reflektory LED / przeciwmgielne, sygnalizator pieszych, tempomat z ogranicznikiem.
   - "equipment_comfort_extras": klimatyzacja, fotele, fotel amortyzowany, podłokietnik, składany stolik / funkcja mobilnego biura, tapicerka, kierownica skórzana, elektryczne i podgrzewane lusterka, elektryczne szyby, półka pod sufitem, schowki (pod fotelem / między fotelami), uchwyty na kubki, centralny zamek, wspomaganie kierownicy, deska rozdzielcza.
   - "equipment_other": wyposażenie dostawcze, ładunkowe i konstrukcyjne (drzwi tylne dwuskrzydłowe / otwierane 270°, drzwi przesuwne, trwała przegroda z blachy, oświetlenie LED ładowni, gniazdo 12V w ładowni, uchwyty mocowania ładunku, dach podwyższony, wzmocnione zawieszenie, resory, koło zapasowe z koszem, zestaw Fix&Go, felgi stalowe/aluminiowe, opony, zderzak, grill w kolorze, listwy ochronne, zbiornik paliwa (np. 90L), alternator, akumulator, pakiety opcji (Pakiet Magic Fiat, Pakiet Safety, Pakiet Cargo, Pakiet Techno), instrukcja obsługi).

Zwróć WYŁĄCZNIE poprawny obiekt JSON z polami: "equipment_audio_multimedia", "equipment_safety", "equipment_comfort_extras", "equipment_other" (każde pole to tablica unikalnych stringów).

SUROWE WYPOSAŻENIE:
{json.dumps(raw_items, ensure_ascii=False, indent=2)}
"""

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": "https://car-scout.pl",
            "X-Title": "Auto-Scraper Car-Scout"
        }

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                },
                timeout=45
            )
            if resp.status_code == 200:
                res_data = resp.json()
                content = res_data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return {
                    "equipment_audio_multimedia": "|".join(parsed.get("equipment_audio_multimedia", [])),
                    "equipment_safety": "|".join(parsed.get("equipment_safety", [])),
                    "equipment_comfort_extras": "|".join(parsed.get("equipment_comfort_extras", [])),
                    "equipment_other": "|".join(parsed.get("equipment_other", []))
                }
            else:
                self.logger.warning(f"OpenRouter zwrócił kod {resp.status_code}: {resp.text[:150]}, używam fallbacku")
        except Exception as e:
            self.logger.warning(f"Błąd wywołania OpenRouter LLM: {e}, przełączam na regułowy fallback")

        return self._categorize_fallback(raw_items)

    def _categorize_fallback(self, raw_items: list[str]) -> dict:
        """
        Deterministyczny fallback kategoryzacji, gdy LLM jest niedostępny.
        Gwarantuje, że żadna opcja nie zostanie pominięta.
        """
        cat_map = {
            "audio": [],
            "safety": [],
            "comfort": [],
            "other": []
        }

        for item in raw_items:
            ilow = item.lower()
            if any(k in ilow for k in ["radio", "audio", "bluetooth", "dab", "usb", "carplay", "android auto", "nawigacj", "kamera cofania", "telematycz", "głośnomów"]):
                cat_map["audio"].append(item)
            elif any(k in ilow for k in ["poduszk", "pasów", "pasy", "abs", "esp", "esc", "asr", "pre-collision", "martw", "zapięcia", "zmęczeni", "zmian", "asystent", "tpms", "ciśnieni", "przeciwmgiel", "dzienn", "reflektor", "sygnał dźwiękow", "tempomat"]):
                cat_map["safety"].append(item)
            elif any(k in ilow for k in ["klimatyzacj", "fotel", "siedzeni", "podłokietnik", "lusterk", "szyb", "stolik", "biur", "tapicerk", "kierownic", "półka pod sufitem", "schowek", "uchwyt", "centralny zamek", "wspomaganie"]):
                cat_map["comfort"].append(item)
            else:
                cat_map["other"].append(item)

        return {
            "equipment_audio_multimedia": "|".join(cat_map["audio"]),
            "equipment_safety": "|".join(cat_map["safety"]),
            "equipment_comfort_extras": "|".join(cat_map["comfort"]),
            "equipment_other": "|".join(cat_map["other"])
        }

    def parse_offer(self, url: str) -> dict:
        """
        Parsuje pojedynczą ofertę z fiat.pgd.pl i zwraca ustandaryzowany słownik danych.
        """
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Identyfikatory
        listing_id_match = re.search(r"/id/(\d+)", url)
        listing_id = listing_id_match.group(1) if listing_id_match else ""

        # 2. Tytuł i Wersja
        title_el = soup.find("h1", class_="text-primary")
        full_title = title_el.text.strip() if title_el else ""

        # Wyodrębnienie marki, modelu i wersji
        marka = "Fiat"
        model = ""
        wersja = ""

        title_upper = full_title.upper()
        if "DUCATO" in title_upper:
            model = "Ducato"
        elif "DOBLO" in title_upper or "DOBLÒ" in title_upper:
            model = "Doblo"
        elif "SCUDO" in title_upper:
            model = "Scudo"
        elif "FIORINO" in title_upper:
            model = "Fiorino"
        elif "PANDA" in title_upper:
            model = "Panda"
        elif "600" in title_upper:
            model = "600"
        elif "500" in title_upper:
            model = "500"

        if model:
            pattern = re.compile(rf"^FIAT\s+{model}\s*", re.IGNORECASE)
            wersja = pattern.sub("", full_title).strip()
        else:
            wersja = full_title

        # 3. Atrybuty ze specyfikacji bocznej
        attrs = {}
        for attr_el in soup.select(".attributes .attribute, .attribute"):
            text = attr_el.text.strip()
            if ":" in text:
                k, v = text.split(":", 1)
                attrs[k.strip()] = v.strip()

        # Numer oferty i VIN
        numer_oferty = attrs.get("Numer oferty") or listing_id
        vin = attrs.get("Numer VIN") or ""

        # Rocznik i Przebieg
        rocznik = self._safe_int(attrs.get("Rok produkcji"))
        przebieg_raw = attrs.get("Przebieg")
        przebieg_km = self._safe_int(przebieg_raw) if przebieg_raw else None

        # Silnik i Pojemność
        silnik_raw = attrs.get("Silnik", "").lower()
        typ_silnika = "Diesel" if "diesel" in silnik_raw else ("Elektryczny" if "elektrycz" in silnik_raw else ("Benzynowy" if "benzyn" in silnik_raw else ("Hybryda" if "hybryd" in silnik_raw else silnik_raw.capitalize())))
        
        moc_km = self._safe_int(attrs.get("Moc"))
        pojemnosc_cm3 = self._parse_capacity(attrs.get("Pojemność"))

        # Nadwozie, Kolor, Lakier
        typ_nadwozia = attrs.get("Rodzaj", "").capitalize() or "Dostawczy"
        kolor_nadwozia_raw = attrs.get("Kolor nadwozia", "")
        kolor = kolor_nadwozia_raw
        paint_type = ""
        if "  " in kolor_nadwozia_raw or "(" in kolor_nadwozia_raw:
            parts = re.split(r"\s{2,}|\s*\(|\)", kolor_nadwozia_raw)
            parts = [p.strip() for p in parts if p.strip()]
            if parts:
                kolor = parts[0].capitalize()
                paint_type = " ".join(parts[1:])
        elif " " in kolor_nadwozia_raw:
            words = kolor_nadwozia_raw.split()
            kolor = words[0].capitalize()
            paint_type = " ".join(words[1:])

        # 4. Ceny
        prices_block = soup.find(class_="prices")
        cena_netto_pln = None
        stara_cena_pln = None
        omnibus_lowest_30d_pln = None
        omnibus_text = ""
        price_display = ""

        if prices_block:
            primary_price_el = prices_block.find(class_="btn-primary")
            if primary_price_el:
                price_text = primary_price_el.text.strip()
                cena_netto_pln = self._safe_int(price_text)
                price_display = price_text

            strikethrough_el = prices_block.find(class_="text-line-through")
            if strikethrough_el:
                stara_cena_pln = self._safe_int(strikethrough_el.text.strip())

            omnibus_el = prices_block.find(class_="omnibus-price")
            if omnibus_el:
                omnibus_text = re.sub(r"\s+", " ", omnibus_el.text).strip()
                omnibus_lowest_30d_pln = self._parse_omnibus(omnibus_text)

        # Obliczenie ceny brutto (netto * 1.23 dla aut ciężarowych/dostawczych)
        cena_brutto_pln = int(round(cena_netto_pln * 1.23)) if cena_netto_pln else None

        # 5. Galeria zdjęć
        images = []
        for li in soup.select("#slider .slides li a, #slider .slides li img"):
            src = li.get("href") or li.get("src")
            if src:
                full_img_url = urljoin(self.base_url, src)
                if full_img_url not in images and "logo" not in full_img_url and "favicon" not in full_img_url:
                    images.append(full_img_url)

        primary_image_url = images[0] if images else ""
        image_count = len(images)
        image_urls_str = " | ".join(images)

        # 6. Pełne wyposażenie i kategoryzacja (LLM + Fallback)
        all_raw_equipment = self._extract_all_raw_equipment(soup)
        if self.use_llm and self.openrouter_api_key:
            eq_categorized = self._categorize_with_llm(all_raw_equipment)
        else:
            eq_categorized = self._categorize_fallback(all_raw_equipment)

        # 7. Dodatkowe informacje / Pełny opis
        add_info_h3 = soup.find(lambda e: e.name == "h3" and "dodatkowe informacje" in e.text.lower())
        description_lines = []
        if add_info_h3:
            curr = add_info_h3.find_next_sibling()
            while curr:
                if curr.name in ["p", "ul", "div", "h4"] and not curr.find(class_="box-contact"):
                    text = curr.text.strip()
                    if text and "kontakt" not in text.lower():
                        cleaned_line = re.sub(r"[ \t]+", " ", text)
                        description_lines.append(cleaned_line)
                curr = curr.find_next_sibling()

        additional_info_header = "Dodatkowe informacje"
        additional_info_content = "\n".join(description_lines)

        # Skrzynia biegów
        skrzynia_raw = attrs.get("Skrzynia", "").lower()
        if not skrzynia_raw:
            combined_desc = f"{full_title} {additional_info_content}".lower()
            if any(k in combined_desc for k in ["automat", "at8", "eat8", "at9", "automatyczna", "reduktor"]) or typ_silnika == "Elektryczny":
                skrzynia_raw = "automatyczna"
            elif any(k in combined_desc for k in ["manual", "mt6", "mt5", "manualna", "6-bieg", "5-bieg"]):
                skrzynia_raw = "manualna"
        skrzynia_biegow = "Automatyczna" if "automat" in skrzynia_raw else ("Manualna" if "manual" in skrzynia_raw else skrzynia_raw.capitalize() if skrzynia_raw else "Manualna")

        # Wzbogacenie brakujących pól z opisu
        if rocznik is None:
            yr_match = re.search(r"Rok produkcji:\s*(\d{4})", additional_info_content, re.IGNORECASE)
            if yr_match:
                rocznik = int(yr_match.group(1))

        if przebieg_km is None:
            if "bez przebiegu" in additional_info_content.lower() or "fabrycznie now" in additional_info_content.lower():
                przebieg_km = 0

        first_reg_match = re.search(r"zarejestrowan[ey]\s+.*?(\d{2}[.-]\d{2}[.-]\d{4})", additional_info_content, re.IGNORECASE)
        first_registration_date = first_reg_match.group(1) if first_reg_match else ""

        seats = 3
        doors = 4
        if "brygadowy" in full_title.lower() or "crewcab" in full_title.lower():
            seats = 5
            doors = 5

        # 8. Dane Dealera
        dealer_name = "Fiat PGD Warszawa"
        dealer_street = "Krasnobrodzka 5"
        dealer_city = "Warszawa"
        dealer_postcode = "03-214"
        dealer_address_line1 = dealer_street
        dealer_address_line2 = dealer_city
        dealer_address_line3 = "Trasa Toruńska przy rondzie Łabiszyńska"
        dealer_google_link = "https://fiat.pgd.pl/p/o-nas/kontakt"
        contact_phone = "123 000 055"

        box_contact = soup.find(class_="box-contact")
        if box_contact:
            box_text = box_contact.text
            phone_match = re.search(r"(\d{3}\s*\d{3}\s*\d{3})", box_text)
            if phone_match:
                contact_phone = phone_match.group(1)

        # 9. JSON ze wszystkimi specyfikacjami
        all_specs = dict(attrs)
        all_specs.update({
            "Tytuł oferty": full_title,
            "Cena netto": f"{cena_netto_pln} PLN" if cena_netto_pln else "",
            "Cena brutto (kalkulacja)": f"{cena_brutto_pln} PLN" if cena_brutto_pln else "",
            "Cena katalogowa netto": f"{stara_cena_pln} PLN" if stara_cena_pln else "",
            "Najniższa cena 30d": f"{omnibus_lowest_30d_pln} PLN" if omnibus_lowest_30d_pln else "",
            "Liczba pozycji wyposażenia": len(all_raw_equipment)
        })
        specs_json = json.dumps(all_specs, ensure_ascii=False)

        now_iso = datetime.now(timezone.utc).isoformat()

        return {
            "listing_id": listing_id,
            "numer_oferty": numer_oferty,
            "url": url,
            "listing_url": url,
            "scraped_at": now_iso,
            "marka": marka,
            "make": marka,
            "model": model,
            "wersja": wersja,
            "version": wersja,
            "vin": vin,
            "cena_brutto_pln": cena_brutto_pln,
            "cena_netto_pln": cena_netto_pln,
            "price_pln": cena_brutto_pln,
            "price_display": price_display,
            "stara_cena_pln": stara_cena_pln,
            "omnibus_lowest_30d_pln": omnibus_lowest_30d_pln,
            "omnibus_text": omnibus_text,
            "rocznik": rocznik,
            "production_year": rocznik,
            "przebieg_km": przebieg_km,
            "mileage_km": przebieg_km,
            "typ_silnika": typ_silnika,
            "fuel_type": typ_silnika,
            "skrzynia_biegow": skrzynia_biegow,
            "transmission": skrzynia_biegow,
            "moc_km": moc_km,
            "engine_power_hp": moc_km,
            "registration_number": "",
            "pierwsza_rejestracja": first_registration_date,
            "first_registration_date": first_registration_date,
            "pojemnosc_cm3": pojemnosc_cm3,
            "engine_capacity_cm3": pojemnosc_cm3,
            "naped": "Przedni",
            "drive": "Przedni",
            "typ_nadwozia": typ_nadwozia,
            "body_type": typ_nadwozia,
            "ilosc_drzwi": str(doors),
            "doors": str(doors),
            "seats": seats,
            "kolor": kolor,
            "color": kolor,
            "paint_type": paint_type,
            "dealer_name": dealer_name,
            "dealer_street": dealer_street,
            "dealer_postcode": dealer_postcode,
            "dealer_city": dealer_city,
            "dealer_address_line1": dealer_address_line1,
            "dealer_address_line2": dealer_address_line2,
            "dealer_address_line3": dealer_address_line3,
            "dealer_google_rating": None,
            "dealer_review_count": None,
            "dealer_google_link": dealer_google_link,
            "contact_phone": contact_phone,
            "primary_image_url": primary_image_url,
            "image_count": image_count,
            "zdjecia": image_urls_str,
            "image_urls": image_urls_str,
            "equipment_audio_multimedia": eq_categorized["equipment_audio_multimedia"],
            "equipment_safety": eq_categorized["equipment_safety"],
            "equipment_comfort_extras": eq_categorized["equipment_comfort_extras"],
            "equipment_other": eq_categorized["equipment_other"],
            "additional_info_header": additional_info_header,
            "additional_info_content": additional_info_content,
            "specs_json": specs_json,
            "source": "fiat.pgd.pl"
        }

    def to_car_scout_row(self, data: dict) -> dict:
        """
        Mapuje sparsowane dane do formatu wymaganego przez standard car-scout CSV.
        """
        return {
            "listing_id": data.get("listing_id") or data.get("numer_oferty") or "",
            "listing_url": data.get("url") or data.get("listing_url") or "",
            "scraped_at": data.get("scraped_at") or "",
            "make": data.get("marka") or data.get("make") or "Fiat",
            "model": data.get("model") or "",
            "version": data.get("wersja") or data.get("version") or "",
            "vin": data.get("vin") or "",
            "price_pln": data.get("cena_brutto_pln") if data.get("cena_brutto_pln") is not None else (data.get("cena_netto_pln") or ""),
            "price_display": data.get("price_display") or "",
            "omnibus_lowest_30d_pln": data.get("omnibus_lowest_30d_pln") if data.get("omnibus_lowest_30d_pln") is not None else "",
            "omnibus_text": data.get("omnibus_text") or "",
            "production_year": data.get("rocznik") or data.get("production_year") or "",
            "mileage_km": data.get("przebieg_km") if data.get("przebieg_km") is not None else 0,
            "fuel_type": data.get("typ_silnika") or data.get("fuel_type") or "",
            "transmission": data.get("skrzynia_biegow") or data.get("transmission") or "",
            "engine_power_hp": data.get("moc_km") or data.get("engine_power_hp") or "",
            "registration_number": data.get("registration_number") or "",
            "first_registration_date": data.get("pierwsza_rejestracja") or data.get("first_registration_date") or "",
            "engine_capacity_cm3": data.get("pojemnosc_cm3") if data.get("pojemnosc_cm3") is not None else "",
            "drive": data.get("naped") or data.get("drive") or "",
            "body_type": data.get("typ_nadwozia") or data.get("body_type") or "",
            "doors": data.get("ilosc_drzwi") or data.get("doors") or "",
            "seats": data.get("seats") if data.get("seats") is not None else "",
            "color": data.get("kolor") or data.get("color") or "",
            "paint_type": data.get("paint_type") or "",
            "dealer_name": data.get("dealer_name") or "",
            "dealer_address_line1": data.get("dealer_address_line1") or "",
            "dealer_address_line2": data.get("dealer_address_line2") or "",
            "dealer_address_line3": data.get("dealer_address_line3") or "",
            "dealer_google_rating": data.get("dealer_google_rating") or "",
            "dealer_review_count": data.get("dealer_review_count") or "",
            "dealer_google_link": data.get("dealer_google_link") or "",
            "contact_phone": data.get("contact_phone") or "",
            "primary_image_url": data.get("primary_image_url") or "",
            "image_count": data.get("image_count") or 0,
            "image_urls": data.get("zdjecia") or data.get("image_urls") or "",
            "equipment_audio_multimedia": data.get("equipment_audio_multimedia") or "",
            "equipment_safety": data.get("equipment_safety") or "",
            "equipment_comfort_extras": data.get("equipment_comfort_extras") or "",
            "equipment_other": data.get("equipment_other") or "",
            "additional_info_header": data.get("additional_info_header") or "",
            "additional_info_content": data.get("additional_info_content") or "",
            "specs_json": data.get("specs_json") or ""
        }
