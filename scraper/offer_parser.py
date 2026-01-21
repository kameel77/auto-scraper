"""
Offer Parser - parsuje pojedynczą stronę oferty
"""
import re
import json
import logging
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Session dla wszystkich requestów
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
})


def _norm_space(s: str) -> str:
    """Normalizuje białe znaki w stringu."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _to_int_pl(s: str) -> int | None:
    """
    Konwertuje polską liczbę do int.
    Przykład: "122 900 zł" -> 122900
    """
    if not s:
        return None
    s = s.replace("\xa0", " ")
    m = re.search(r"([\d\s]+)", s)
    if not m:
        return None
    try:
        return int(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def _extract_by_label(soup: BeautifulSoup, label: str) -> str | None:
    """
    Szuka etykiety w HTML i zwraca wartość po niej.
    
    Args:
        soup: BeautifulSoup object
        label: Tekst etykiety do znalezienia (np. 'Rocznik:')
    
    Returns:
        Wartość znaleziona po etykiecie lub None
    """
    # Szukaj dokładnego dopasowania tekstu
    node = soup.find(string=lambda t: t and _norm_space(t) == label)
    if not node:
        return None
    
    # Przeszukaj następne elementy w poszukiwaniu wartości
    cur = node
    for _ in range(10):
        if not hasattr(cur, "parent"):
            break
        cur = cur.parent
        nxt = cur.find_next()
        if not nxt:
            break
        txt = _norm_space(nxt.get_text(" ", strip=True))
        # Upewnij się, że to nie jest kolejna etykieta
        if txt and txt != label and not txt.endswith(":"):
            # Dodatkowa walidacja - nie zwracaj innych labelek
            if txt.lower() not in ["numer oferty:", "rocznik:", "vin:", "przebieg:", "typ nadwozia:"]:
                return txt
        cur = nxt
    
    return None


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(requests.RequestException),
)
def fetch_html(url: str) -> str:
    """Pobiera HTML strony z retry logic."""
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def _extract_json_data(html: str) -> dict | None:
    """
    Wyciąga i parsuje dane JSON z window.__NUXT__ w HTML.
    
    Args:
        html: Kod HTML strony
        
    Returns:
        Słownik z danymi JSON lub None jeśli nie znaleziono
    """
    # Szukaj window.__NUXT__
    pattern = r'window\.__NUXT__\s*=\s*(\(function\([^)]*\)\{[^}]+\}\)\([^)]*\));'
    match = re.search(pattern, html)
    
    if not match:
        logger.warning("Nie znaleziono window.__NUXT__ w HTML")
        return None
    
    try:
        # Wyciągnij samo wywołanie funkcji
        js_code = match.group(1)
        
        # Dla uproszczenia, spróbujmy znaleźć strukturę data.vehicle
        # Alternatywnie: uruchom JS w subprocess, ale to komplikuje
        # Lepsze podejście: znajdź JSON bezpośrednio w strukturze
        
        # Szukamy sekcji z danymi pojazdu
        vehicle_pattern = r'vehicle:\{id:(\d+),attributes:\[([^\]]+)'
        vehicle_match = re.search(vehicle_pattern, html)
        
        if vehicle_match:
            logger.info("Znaleziono dane pojazdu w window.__NUXT__")
            return {"found": True, "vehicle_id": vehicle_match.group(1)}
        
        return None
        
    except Exception as e:
        logger.error(f"Błąd parsowania JSON: {e}")
        return None


def _extract_nuxt_map(html: str) -> dict:
    """
    Wyciąga mapowanie zmiennych (a, b, c...) na wartości z window.__NUXT__.
    Używa rfind do precyzyjnego znalezienia argumentów wywołania funkcji.
    """
    try:
        # 0. Znajdź blok skryptu window.__NUXT__
        script_match = re.search(r'window\.__NUXT__\s*=\s*(.*?);?\s*</script>', html, re.DOTALL)
        if not script_match:
            # Rezerwowy pattern jeśli script tag ma atrybuty
            script_match = re.search(r'window\.__NUXT__\s*=\s*(.*?);?\n', html, re.DOTALL)
            
        if not script_match:
            return {}
            
        content = script_match.group(1).strip()
        
        # 1. Wyciągnij listę nazw zmiennych (początek skryptu: (function(a,b,...){)
        var_match = re.search(r'^\(function\(([^)]+)\)', content)
        if not var_match:
            # Spróbuj bez nawiasu na początku
            var_match = re.search(r'^function\(([^)]+)\)', content)
        
        if not var_match:
            logger.warning("Nie znaleziono nazw zmiennych Nuxt")
            return {}
            
        var_names = [v.strip() for v in var_match.group(1).split(',')]
        
        # 2. Wyciągnij listę wartości (koniec skryptu: }(val1,val2,...)))
        # Precyzyjnie szukamy ostatniego }( oraz ostatniego ))
        idx_open = content.rfind('}(')
        idx_close = content.rfind('))')
        
        if idx_open == -1 or idx_close == -1 or idx_close < idx_open:
            # Spróbuj prostszy wzorzec jeśli nie ma podwójnego nawiasu na końcu
            idx_close = content.rfind(')')
            if idx_open == -1 or idx_close == -1 or idx_close < idx_open:
                logger.warning("Nie znaleziono granic wartości Nuxt")
                return {}
            
        values_raw = content[idx_open + 2 : idx_close]
        
        # Podział wartości z obsługą cudzysłowów i zagnieżdżonych struktur
        values = []
        current = []
        in_quotes = False
        quote_char = None
        nest_level = 0
        
        for char in values_raw:
            if char in ('"', "'"):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
            
            if not in_quotes:
                if char in ('{', '['): nest_level += 1
                elif char in ('}', ']'): nest_level -= 1
            
            if char == ',' and not in_quotes and nest_level == 0:
                values.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        values.append("".join(current).strip())
        
        # Mapuj nazwy na wartości
        nuxt_map = {}
        for i, name in enumerate(var_names):
            if i < len(values):
                val = values[i]
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                elif val == "null": val = None
                elif val == "true": val = True
                elif val == "false": val = False
                elif val.isdigit(): val = int(val)
                nuxt_map[name] = val
                
        return nuxt_map
    except Exception as e:
        logger.error(f"Błąd podczas extract_nuxt_map: {e}")
        return {}


def _extract_vehicle_attributes(html: str) -> dict:
    """
    Wyciąga atrybuty pojazdu z window.__NUXT__.
    """
    nuxt_map = _extract_nuxt_map(html)
    attributes = {}
    
    # Mapowanie ID atrybutów Nuxt na klucze słownika
    attr_ids = {
        58: "marka", 59: "model", 196: "wersja", 195: "numer_oferty", 
        197: "vin", 81: "rocznik", 1157: "pierwsza_rejestracja", 
        82: "przebieg_km", 63: "typ_nadwozia", 66: "typ_silnika", 
        70: "pojemnosc_cm3", 71: "moc_km", 247: "naped", 
        242: "skrzynia_biegow", 87: "kolor", 64: "ilosc_drzwi", 
        77: "cena_brutto_pln", 78: "stara_cena_pln", 1142: "tytul"
    }

    # Wzorzec szukający atrybutów w JSON-opodobnym formacie Nuxt
    # Regex jest liberalny co do wartości (zmienna lub string)
    pattern = r'\{id:(\d+),type:([^,]+),name:"([^"]+)",value:([^,]+),group:([^}]+)\}'
    
    for match in re.finditer(pattern, html):
        attr_id = int(match.group(1))
        if attr_id in attr_ids:
            key = attr_ids[attr_id]
            val_raw = match.group(4).strip()
            
            # Pobierz z mapy zmiennych lub użyj surowej wartości
            val = nuxt_map.get(val_raw, val_raw)
            if isinstance(val, str):
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
            
            # Próba konwersji na int dla pól numerycznych
            if val is not None:
                if key in ["rocznik", "przebieg_km", "pojemnosc_cm3", "moc_km", "cena_brutto_pln", "stara_cena_pln"]:
                    try:
                        # Usuń spacje i ewentualne jednostki
                        clean_val = str(val).replace(" ", "").replace("\xa0", "")
                        match_num = re.search(r'(\d+)', clean_val)
                        if match_num:
                            val = int(match_num.group(1))
                    except: pass
            
            attributes[key] = val
            
    return attributes


def _extract_grouped_equipment(html: str) -> dict:
    """
    Wyciąga wyposażenie pogrupowane według kategorii z window.__NUXT__.
    """
    nuxt_map = _extract_nuxt_map(html)
    
    groups_data = {
        "technologia": [], "komfort": [], "bezpieczenstwo": [],
        "wyglad": [], "historia": [], "finanse": []
    }
    
    group_name_map = {
        "technolog": "technologia",
        "multimedi": "technologia",
        "wnetrz": "komfort",
        "komfort": "komfort",
        "bezpiecz": "bezpieczenstwo",
        "nadwozi": "wyglad",
        "wyglad": "wyglad",
        "oswietl": "wyglad",
        "historia": "historia",
        "cena": "finanse",
        "finans": "finanse",
        "inne": "finanse",
        "dodatkow": "finanse"
    }

    pattern = r'\{id:(\d+),type:([^,]+),name:"([^"]+)",value:([^,]+),group:([^}]+)\}'
    
    matches = re.findall(pattern, html)
    logger.info(f"Found {len(matches)} equipment matches in HTML")
    
    for match in matches:
        attr_name = match[2]
        val_raw = match[3].strip()
        group_raw = match[4].strip()
        
        val = nuxt_map.get(val_raw, val_raw)
        is_enabled = val in [True, "1", "true", 1]
        
        if is_enabled:
            group_name = nuxt_map.get(group_raw, group_raw)
            if isinstance(group_name, str):
                if (group_name.startswith('"') and group_name.endswith('"')) or (group_name.startswith("'") and group_name.endswith("'")):
                    group_name = group_name[1:-1]
                
                clean_group = group_name.lower().replace("ą", "a").replace("ć", "c").replace("ę", "e").replace("ł", "l").replace("ń", "n").replace("ó", "o").replace("ś", "s").replace("ź", "z").replace("ż", "z")
                
                for kw, cat in group_name_map.items():
                    if kw.lower() in clean_group:
                        groups_data[cat].append(attr_name)
                        logger.info(f"Added equipment: {attr_name} -> {cat}")
                        break

    result = {
        "wyposazenie_technologia": " | ".join(groups_data["technologia"]) if groups_data["technologia"] else None,
        "wyposazenie_komfort": " | ".join(groups_data["komfort"]) if groups_data["komfort"] else None,
        "wyposazenie_bezpieczenstwo": " | ".join(groups_data["bezpieczenstwo"]) if groups_data["bezpieczenstwo"] else None,
        "wyposazenie_wyglad": " | ".join(groups_data["wyglad"]) if groups_data["wyglad"] else None,
        "dane_historia": " | ".join(groups_data["historia"]) if groups_data["historia"] else None,
        "dane_finanse": " | ".join(groups_data["finanse"]) if groups_data["finanse"] else None,
    }
    
    logger.info(f"Equipment result: {result}")
    return result


def _extract_images_from_json(html: str) -> list[str]:
    """
    Wyciąga listę zdjęć z window.__NUXT__ (files array).
    
    Args:
        html: Kod HTML strony
        
    Returns:
        Lista URL-i zdjęć
    """
    # Szukaj: files:["url1","url2",...]
    pattern = r'files:\[([^\]]+)\]'
    match = re.search(pattern, html)
    
    if not match:
        return []
    
    files_str = match.group(1)
    # Wyciągnij wszystkie URL-e w cudzysłowach
    urls = re.findall(r'"(https?://[^"]+)"', files_str)
    
    return urls


def _extract_location_from_json(html: str, nuxt_map: dict) -> dict:
    """
    Wyciąga dane lokalizacji i dealera z window.__NUXT__ wykorzystując mapowanie.
    Szuka zmiennej przypisanej do 'location' i wyciąga jej właściwości.
    """
    location = {}
    
    # 1. Znajdź nazwę zmiennej dla lokalizacji
    # Szukamy wewnątrz bloku skryptu window.__NUXT__
    script_match = re.search(r'window\.__NUXT__.*?</script>', html, re.DOTALL)
    if not script_match:
        return {}
    
    script_content = script_match.group(0)
    
    # Szukaj 'location:V' gdzie V to zmienna (zazwyczaj jedno- lub dwuliterowa)
    loc_var_match = re.search(r'location:([a-zA-Z_$][0-9a-zA-Z_$]*)', script_content)
    if not loc_var_match:
        # Fallback do bezpośrednich wzorców jeśli nie znaleziono zmiennej
        loc_var = ""
    else:
        loc_var = loc_var_match.group(1)
    
    # 2. Definiujemy wzorce dla właściwości tej zmiennej
    # Jeśli loc_var to 'Q', szukamy 'Q.name=val', 'Q.street=val', etc.
    # Jeśli loc_var jest puste, szukamy 'city:"..."' etc (mniej bezpieczne)
    
    if loc_var:
        # Wzorce dla przypisań typu Q.name=a lub Q.name="Wartość"
        prop_patterns = {
            "lokalizacja_nazwa": rf'{loc_var}\.name\s*=\s*([^;]+);',
            "lokalizacja_miasto": rf'{loc_var}\.city\s*=\s*([^;]+);',
            "lokalizacja_ulica": rf'{loc_var}\.street\s*=\s*([^;]+);',
            "lokalizacja_kod": rf'{loc_var}\.postalCode\s*=\s*([^;]+);',
            "telefon": rf'{loc_var}\.phone\s*=\s*([^;]+);',
        }
    else:
        # Fallback - szukaj słów kluczowych blisko siebie (ryzykowne)
        prop_patterns = {
            "lokalizacja_nazwa": r'name:"([^"]+)"',
            "lokalizacja_miasto": r'city:"([^"]+)"',
            "lokalizacja_ulica": r'street:"([^"]+)"',
            "lokalizacja_kod": r'postalCode:"([^"]+)"',
            "telefon": r'phone:"([^"]+)"',
        }
    
    for key, pattern in prop_patterns.items():
        match = re.search(pattern, script_content)
        if match:
            val_raw = match.group(1).strip()
            val = nuxt_map.get(val_raw, val_raw)
            if isinstance(val, str):
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
            location[key] = val
        else:
            location[key] = None
    
    # 3. Dodatkowe mapowanie i składanie adresu
    location["dealer_name"] = location.get("lokalizacja_nazwa")
    location["dealer_address_line_1"] = location.get("lokalizacja_ulica")
    
    city = location.get("lokalizacja_miasto")
    postal = location.get("lokalizacja_kod")
    street = location.get("lokalizacja_ulica")
    
    if postal and city:
        location["dealer_address_line_2"] = f"{postal} {city}"
    else:
        location["dealer_address_line_2"] = city or postal
        
    # Składanie pełnego adresu
    parts = [p for p in [postal, city, street] if p]
    location["adres"] = ", ".join(parts) if parts else None
    
    location["contact_phone"] = location.get("telefon")
    
    return location


def parse_offer(url: str) -> dict:
    """
    Parsuje stronę oferty i zwraca słownik z danymi.
    Priorytet: JSON extraction z window.__NUXT__, fallback do HTML parsing.
    
    Args:
        url: URL oferty do sparsowania
        
    Returns:
        Słownik z wyparsowanymi danymi oferty
    """
    logger.info(f"Parsowanie: {url}")
    
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "lxml")
        
        # === PRIORYTET 1: Ekstrakcja z JSON ===
        logger.debug("Próba ekstrakcji danych z window.__NUXT__")
        nuxt_map = _extract_nuxt_map(html)
        json_attrs = _extract_vehicle_attributes(html)
        json_equipment = _extract_grouped_equipment(html)
        json_images = _extract_images_from_json(html)
        json_location = _extract_location_from_json(html, nuxt_map)
        
        # Rozpocznij od danych JSON
        data = {"url": url}
        
        # === DANE PODSTAWOWE ===
        # Marka, Model, Wersja - osobne pola
        data["marka"] = json_attrs.get("marka")
        data["model"] = json_attrs.get("model")
        data["wersja"] = json_attrs.get("wersja")
        data["tytul"] = json_attrs.get("tytul")
        data["numer_oferty"] = json_attrs.get("numer_oferty")
        
        # Fallback dla marki/modelu z HTML jeśli JSON nie ma
        if not data["marka"] or not data["model"]:
            html_title = _extract_title(soup)
            if html_title:
                # Spróbuj rozdzielić "Marka Model" na części
                parts = html_title.split(maxsplit=1)
                if not data["marka"] and len(parts) > 0:
                    data["marka"] = parts[0]
                if not data["model"] and len(parts) > 1:
                    data["model"] = parts[1]
        
        # === CENY ===
        data["cena_brutto_pln"] = json_attrs.get("cena_brutto_pln")
        data["stara_cena_pln"] = json_attrs.get("stara_cena_pln")
        
        # HTML fallback dla cen
        if data["cena_brutto_pln"] is None or data["stara_cena_pln"] is None:
            html_prices = _extract_prices(soup)
            if data["cena_brutto_pln"] is None:
                data["cena_brutto_pln"] = html_prices.get("cena_brutto_pln")
            if data["stara_cena_pln"] is None:
                data["stara_cena_pln"] = html_prices.get("stara_cena_pln")
            # Dodaj pozostałe ceny z HTML
            data["najnizsza_cena_30dni_pln"] = html_prices.get("najnizsza_cena_30dni_pln")
            data["korzysc_pln"] = html_prices.get("korzysc_pln")
            data["rata_kredytu_pln_mies"] = html_prices.get("rata_kredytu_pln_mies")
        else:
            # Jeśli mamy JSON, wylicz korzyść
            if data["stara_cena_pln"] and data["cena_brutto_pln"]:
                data["korzysc_pln"] = data["stara_cena_pln"] - data["cena_brutto_pln"]
            else:
                data["korzysc_pln"] = None
            data["najnizsza_cena_30dni_pln"] = None
            data["rata_kredytu_pln_mies"] = None
        
        # === DANE TECHNICZNE ===
        data["rocznik"] = json_attrs.get("rocznik")
        data["pierwsza_rejestracja"] = json_attrs.get("pierwsza_rejestracja")
        data["vin"] = json_attrs.get("vin")
        data["przebieg_km"] = json_attrs.get("przebieg_km")
        data["typ_nadwozia"] = json_attrs.get("typ_nadwozia")
        data["typ_silnika"] = json_attrs.get("typ_silnika")
        data["pojemnosc_cm3"] = json_attrs.get("pojemnosc_cm3")
        data["moc_km"] = json_attrs.get("moc_km")
        data["naped"] = json_attrs.get("naped")
        data["skrzynia_biegow"] = json_attrs.get("skrzynia_biegow")
        data["kolor"] = json_attrs.get("kolor")
        data["ilosc_drzwi"] = json_attrs.get("ilosc_drzwi")
        
        # HTML fallback dla danych technicznych
        if not data["rocznik"] or not data["vin"]:
            html_tech = _extract_technical_data(soup)
            for key in ["rocznik", "pierwsza_rejestracja", "vin", "przebieg_km", 
                       "typ_nadwozia", "typ_silnika", "pojemnosc_cm3", "moc_km",
                       "naped", "skrzynia_biegow", "kolor"]:
                if not data.get(key):
                    data[key] = html_tech.get(key)
        
        # === LOKALIZACJA I KONTAKT ===
        data["lokalizacja_nazwa"] = json_location.get("lokalizacja_nazwa")
        data["lokalizacja_miasto"] = json_location.get("lokalizacja_miasto")
        data["adres"] = json_location.get("adres")
        data["telefon"] = json_location.get("telefon")
        
        # Nowe pola dealera
        data["dealer_name"] = json_location.get("dealer_name")
        data["dealer_address_line_1"] = json_location.get("dealer_address_line_1")
        data["dealer_address_line_2"] = json_location.get("dealer_address_line_2")
        data["contact_phone"] = json_location.get("contact_phone")
        
        # HTML fallback dla lokalizacji
        if not data["lokalizacja_nazwa"] or not data["telefon"]:
            html_location = _extract_location_contact(soup)
            if not data["lokalizacja_nazwa"]:
                data["lokalizacja_nazwa"] = html_location.get("lokalizacja_nazwa")
            if not data["adres"]:
                data["adres"] = html_location.get("adres")
            if not data["telefon"]:
                data["telefon"] = html_location.get("telefon")
        
        # === WYPOSAŻENIE POGRUPOWANE ===
        data["wyposazenie_technologia"] = json_equipment.get("wyposazenie_technologia")
        data["wyposazenie_komfort"] = json_equipment.get("wyposazenie_komfort")
        data["wyposazenie_bezpieczenstwo"] = json_equipment.get("wyposazenie_bezpieczenstwo")
        data["wyposazenie_wyglad"] = json_equipment.get("wyposazenie_wyglad")
        data["dane_historia"] = json_equipment.get("dane_historia")
        data["dane_finanse"] = json_equipment.get("dane_finanse")
        
        # HTML fallback - jeśli JSON nie ma wyposażenia, użyj starej metody
        if not data["wyposazenie_technologia"] and not data["wyposazenie_komfort"]:
            logger.debug("Brak danych wyposażenia z JSON, używam HTML fallback")
            html_features = _extract_features_tags(soup)
            # Stare wyposażenie jako "ogólne" - dodaj jako backup
            data["wyposazenie_inne"] = html_features.get("wyposazenie")
            data["tagi_oferty"] = html_features.get("tagi_oferty")
        else:
            data["wyposazenie_inne"] = None
            # Tagi mogą być w HTML
            html_features = _extract_features_tags(soup)
            data["tagi_oferty"] = html_features.get("tagi_oferty")
        
        # === ZDJĘCIA ===
        if json_images:
            # Filtruj tylko prawdziwe zdjęcia pojazdu (nie ikony, mapy, SVG)
            filtered_images = [
                img for img in json_images 
                if img.startswith("http") 
                and not any(skip in img.lower() for skip in ["icon", "facebook", "statichttps://maps", "data:image/svg"])
                and "/cars/" in img  # Tylko zdjęcia z /cars/
            ]
            data["zdjecia"] = " | ".join(filtered_images) if filtered_images else None
        else:
            # HTML fallback
            data["zdjecia"] = _extract_images(soup, url)
        
        # === METADANE ===
        data["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # === METADANE ===
        data["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["source"] = "autopunkt.pl"
        
        logger.debug(f"Wyekstraktowano {len([v for v in data.values() if v])} pól z danymi")
        return data
        
    except Exception as e:
        logger.error(f"Błąd parsowania {url}: {e}")
        raise



def _extract_title(soup: BeautifulSoup) -> str | None:
    """Wyciąga tytuł główny (marka i model)."""
    h1 = soup.find("h1")
    if h1:
        return _norm_space(h1.get_text(" ", strip=True))
    return None


def _extract_subtitle(soup: BeautifulSoup) -> str | None:
    """Wyciąga podtytuł/wariant."""
    h1 = soup.find("h1")
    if not h1:
        return None
    
    marka_model = _norm_space(h1.get_text(" ", strip=True))
    
    # Szukaj pierwszego sensownego tekstu po h1
    for cand in h1.find_all_next(limit=20):
        txt = _norm_space(cand.get_text(" ", strip=True))
        if txt and txt != marka_model and len(txt) > 10 and len(txt) < 200:
            # Sprawdź czy to nie jest etykieta
            if not txt.endswith(":"):
                return txt
    
    return None


def _extract_prices(soup: BeautifulSoup) -> dict:
    """Wyciąga wszystkie ceny z oferty."""
    text = soup.get_text("\n", strip=True)
    
    def find_price_after(needle: str) -> int | None:
        """Znajduje cenę po danym tekście."""
        idx = text.find(needle)
        if idx < 0:
            return None
        chunk = text[idx: idx + 250]
        m = re.search(r"(\d[\d\s\xa0]*\d)\s*zł", chunk)
        return _to_int_pl(m.group(0)) if m else None
    
    return {
        "cena_brutto_pln": find_price_after("Cena brutto"),
        "najnizsza_cena_30dni_pln": find_price_after("Najniższa cena z 30 dni"),
        "stara_cena_pln": find_price_after("Stara cena"),
        "korzysc_pln": find_price_after("Korzyść"),
        "rata_kredytu_pln_mies": find_price_after("Rata kredytu"),
    }


def _extract_technical_data(soup: BeautifulSoup) -> dict:
    """Wyciąga dane techniczne pojazdu."""
    # Podstawowe pola
    rocznik = _extract_by_label(soup, "Rocznik:")
    data = {
        "rocznik": int(rocznik) if rocznik and rocznik.isdigit() else rocznik,
        "pierwsza_rejestracja": _extract_by_label(soup, "Pierwsza rejestracja:"),
        "vin": _extract_by_label(soup, "VIN:"),
        "typ_nadwozia": _extract_by_label(soup, "Typ nadwozia:"),
        "typ_silnika": _extract_by_label(soup, "Typ silnika:"),
        "naped": _extract_by_label(soup, "Napęd:"),
        "skrzynia_biegow": _extract_by_label(soup, "Skrzynia biegów:"),
        "kolor": _extract_by_label(soup, "Kolor nadwozia:"),
    }
    
    # Przebieg
    przebieg = _extract_by_label(soup, "Przebieg:")
    data["przebieg_km"] = None
    if przebieg:
        m = re.search(r"([\d\s]+)\s*km", przebieg.replace("\xa0", " "))
        if m:
            data["przebieg_km"] = int(m.group(1).replace(" ", ""))
    
    # Pojemność i moc
    poj_moc = _extract_by_label(soup, "Pojemność / moc:")
    data["pojemnosc_cm3"] = None
    data["moc_km"] = None
    if poj_moc:
        m1 = re.search(r"([\d\s]+)\s*\[?CM3\]?", poj_moc, re.I)
        m2 = re.search(r"([\d\s]+)\s*\[?KM\]?", poj_moc, re.I)
        if m1:
            data["pojemnosc_cm3"] = int(m1.group(1).replace(" ", ""))
        if m2:
            data["moc_km"] = int(m2.group(1).replace(" ", ""))
    
    return data


def _extract_location_contact(soup: BeautifulSoup) -> dict:
    """Wyciąga lokalizację i dane kontaktowe."""
    text = soup.get_text("\n", strip=True)
    
    # Telefon
    telefon = None
    m = re.search(r"\bTelefon\b\s*([\d\s]{7,})", text)
    if m:
        telefon = _norm_space(m.group(1))
    
    # Lokalizacja
    lokalizacja_nazwa, adres = None, None
    loc_idx = text.find("Lokalizacja")
    if loc_idx >= 0:
        loc_chunk = text[loc_idx: loc_idx + 400]
        lines = [l.strip() for l in loc_chunk.split("\n") if l.strip()]
        try:
            i = lines.index("Lokalizacja")
            if i + 1 < len(lines):
                lokalizacja_nazwa = lines[i + 1]
            addr_parts = []
            for j in range(i + 2, min(i + 6, len(lines))):
                if any(k in lines[j] for k in ["Podobne oferty", "Zapytaj o ofertę", "Zobacz"]):
                    break
                addr_parts.append(lines[j])
            if addr_parts:
                adres = " ".join(addr_parts)
        except (ValueError, IndexError):
            pass
    
    return {
        "lokalizacja_nazwa": lokalizacja_nazwa,
        "adres": adres,
        "telefon": telefon,
    }


def _extract_features_tags(soup: BeautifulSoup) -> dict:
    """Wyciąga wyposażenie i tagi oferty."""
    uls = soup.find_all("ul")
    
    # Wyposażenie - największa lista z typowymi elementami
    wyposazenie = []
    best = None
    best_score = -1
    
    for ul in uls:
        lis = [_norm_space(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
        if len(lis) < 8:
            continue
        
        joined = " | ".join(lis).lower()
        score = len(lis)
        
        # Boost jeśli zawiera typowe elementy wyposażenia
        if any(keyword in joined for keyword in ["abs", "klimatyzacja", "esp", "airbag"]):
            score += 50
        
        if score > best_score:
            best_score = score
            best = lis
    
    if best:
        wyposazenie = [x for x in best if x and len(x) <= 120]
    
    # Tagi oferty (Bezwypadkowy, Gwarantowany przebieg, etc.)
    tagi = []
    for ul in uls:
        lis = [_norm_space(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
        if 2 <= len(lis) <= 12:
            joined = " | ".join(lis).lower()
            if any(k in joined for k in ["bezwypad", "gwarant", "kraj pochodzenia", "pierwszego właściciela"]):
                tagi = lis
                break
    
    return {
        "wyposazenie": " | ".join(wyposazenie) if wyposazenie else None,
        "tagi_oferty": " | ".join(tagi) if tagi else None,
    }


def _extract_images(soup: BeautifulSoup, base_url: str) -> str | None:
    """Wyciąga adresy URL zdjęć."""
    img_urls = []
    
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        
        # Filtruj ikony i social media
        if any(skip in src.lower() for skip in ["icon", "instagram", "facebook", "logo"]):
            continue
        
        abs_src = urljoin(base_url, src)
        img_urls.append(abs_src)
    
    # Usuń duplikaty zachowując kolejność
    seen = set()
    unique_imgs = []
    for url in img_urls:
        if url not in seen:
            seen.add(url)
            unique_imgs.append(url)
    
    return " | ".join(unique_imgs) if unique_imgs else None
