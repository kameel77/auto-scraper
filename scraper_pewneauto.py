import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://pewneauto.pl/oferty/_sort/new"
BASE_LISTING_URL = BASE_URL + "?strona={page}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def get_soup(url, session, sleep_time=0.5):
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        time.sleep(sleep_time)
        return BeautifulSoup(resp.text, "lxml")
    except requests.exceptions.RequestException as e:
        print(f"Błąd połączenia: {e}")
        return None

def collect_offer_links(session, max_pages=5, base_url="https://pewneauto.pl"):
    parsed = urlparse(base_url)
    if parsed.scheme and parsed.netloc:
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base_url = base_url.rstrip('/')

    offer_urls = set()
    page = 1

    while page <= max_pages:
        url = f"{base_url}/oferty/_sort/new?strona={page}"
        print(f"Przeszukuję listing: {url}")
        soup = get_soup(url, session)

        if soup is None:
            print(f"  Strona {page} nie istnieje (404) lub wystąpił błąd. Kończę szukanie linków.")
            break

        anchors = soup.find_all("a", href=True)
        page_links = {urljoin(base_url, a['href']) for a in anchors if "/oferta/" in a['href']}

        if not page_links:
            break

        new_links = page_links - offer_urls
        print(f"  Strona {page}: znaleziono {len(page_links)} linków (nowych: {len(new_links)})")

        if not new_links and page > 1:
             break

        offer_urls.update(page_links)
        page += 1
    return sorted(list(offer_urls))

def _to_int_pl(s: str) -> int | None:
    if not s: return None
    s = str(s).replace("\xa0", " ").replace(" ", "")
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return None

def extract_tech_specs(soup):
    data = {}
    tech_section = soup.find("section", class_="vdp-tech")
    if tech_section:
        for li in tech_section.find_all("li"):
            span = li.find("span")
            strong = li.find("strong")
            if span and strong:
                key = span.get_text(strip=True).replace(":", "")
                val = strong.get_text(strip=True)
                val = " ".join(val.split())
                data[key] = val
            elif span:
                key = span.get_text(strip=True).replace(":", "")
                val = li.get_text(strip=True).replace(key, "").strip()
                if val:
                    data[key] = " ".join(val.split())

    if not data:
        # Fallback dla szablonu subdomen dilerskich (np. uzywane.toyota-stalowawola.pl)
        spec_ul = soup.find("ul", class_="vdp__spec")
        if spec_ul:
            for li in spec_ul.find_all("li", class_="vdp__spec__element"):
                small = li.find("small")
                span = li.find("span")
                if small and span:
                    key = small.get_text(strip=True)
                    val = " ".join(span.get_text(strip=True).split())
                    if key and val:
                        data[key] = val
    return data

def extract_equipment_groups(soup):
    eq = {
        "bezpieczenstwo": [],
        "komfort": [],
        "inne": []
    }
    
    eq_section = soup.find("section", class_="vdp-eq")
    if not eq_section:
        # Fallback dla szablonu subdomen dilerskich - płaska lista bez nagłówków grup
        eq_div = soup.find(class_="vdp__eq")
        if eq_div:
            for li in eq_div.find_all("li"):
                eq["inne"].append(li.get_text(strip=True))
        return eq

    # Pewneauto dzieli wyposażenie wg sekcji (h3) w akordeonie
    for section in eq_section.find_all("section"):
        header = section.find("h3")
        if not header:
            continue
        group_name = header.get_text(strip=True).lower()
        
        target_group = "inne"
        if "bezpiecz" in group_name:
            target_group = "bezpieczenstwo"
        elif "komfort" in group_name:
            target_group = "komfort"

        ul = section.find("ul")
        if ul:
            for li in ul.find_all("li"):
                eq[target_group].append(li.get_text(strip=True))

    return eq

def scrape_offer(session, url):
    soup = get_soup(url, session)
    if not soup: return None
    
    # 1. Tytuł, marka, model, wersja
    title_tag = soup.find(class_="vdp__name__title")
    if not title_tag:
        title_tag = soup.find("h1")
    tytul = title_tag.get_text(strip=True) if title_tag else None
    
    marka, model = None, None
    if tytul:
        parts = tytul.split(maxsplit=1)
        if len(parts) > 0: marka = parts[0]
        if len(parts) > 1: model = parts[1]

    subtitle_tag_text = None
    header_title_div = soup.find("div", class_="vdp-header__title")
    if header_title_div:
        strong_tag = header_title_div.find("strong")
        wersja = strong_tag.get_text(strip=True) if strong_tag else None
    else:
        # Fallback
        trim_tag = soup.find(class_=re.compile("subtitle|variant|version", re.I))
        if trim_tag and "vdp__name__subtitle" in trim_tag.get("class", []):
            # Szablon subdomen dilerskich: to nie jest wersja/trim, tylko wolny tekst
            # (np. "Gwarancja Pewne Auto/Serwisowany/..."), więc trafia do tagów oferty
            wersja = None
            subtitle_tag_text = trim_tag.get_text(strip=True)
        else:
            wersja = trim_tag.get_text(strip=True) if trim_tag else None

    # Numer oferty z headera
    numer_oferty = None
    info_div = soup.find("div", class_="vdp-header__info")
    if info_div:
        for span in info_div.find_all("span"):
            if "Numer oferty:" in span.get_text():
                strong = span.find("strong")
                if strong:
                    numer_oferty = strong.get_text(strip=True)

    if not numer_oferty:
        # Fallback dla szablonu subdomen dilerskich: numer jest w URL-u oferty
        m = re.search(r"/oferta/[^/]+/(\d+)", url)
        if m:
            numer_oferty = m.group(1)

    # Diler (Lokalizacja)
    dealer_name = None
    dealer_street = None
    dealer_postcode = None
    dealer_city = None
    dealer_map_link = None
    
    contact_data = soup.find("div", class_="vdp-dealer__contact__data")
    if contact_data:
        address_tag = contact_data.find("address")
        if address_tag:
            strong = address_tag.find("strong")
            if strong:
                dealer_name = strong.get_text(strip=True)
            spans = address_tag.find_all("span")
            if len(spans) > 0:
                dealer_street = spans[0].get_text(strip=True)
            if len(spans) > 1:
                city_line = spans[1].get_text(strip=True) # np. "02-219 Warszawa"
                m = re.match(r"(\d{2}-\d{3})\s+(.*)", city_line)
                if m:
                    dealer_postcode = m.group(1)
                    dealer_city = m.group(2)
                else:
                    dealer_city = city_line
    else:
        # Fallback dla szablonu subdomen dilerskich
        address_tag = soup.find("address", class_="vdp__dealer__info__address")
        if address_tag:
            strong = address_tag.find("strong")
            if strong:
                dealer_name = strong.get_text(strip=True)
            span = address_tag.find("span")
            if span:
                addr_line = span.get_text(strip=True)  # np. "Przemysłowa 5, 37-450 Stalowa Wola"
                if "," in addr_line:
                    left, right = addr_line.split(",", 1)
                    dealer_street = left.strip()
                    right = right.strip()
                    m = re.match(r"(\d{2}-\d{3})\s+(.*)", right)
                    if m:
                        dealer_postcode = m.group(1)
                        dealer_city = m.group(2)
                    else:
                        dealer_city = right
                else:
                    m = re.search(r"(\d{2}-\d{3})\s+(.*)", addr_line)
                    if m:
                        dealer_postcode = m.group(1)
                        dealer_city = m.group(2)

    map_div = soup.find("div", class_="vdp-dealer__map")
    if map_div:
        map_link = map_div.find("a", href=True)
        if map_link:
            dealer_map_link = map_link["href"]

    # Fallback dla starego pobierania
    if not dealer_name:
        loc_label = soup.find(string=re.compile("Lokalizacja|Diler", re.I))
        if loc_label and loc_label.parent:
            val = loc_label.parent.find_next(string=True)
            if val: dealer_name = val.strip()
    # Ceny
    cena_brutto_pln = None
    rata_kredytu_pln_mies = None
    
    price_tag = soup.find(class_=re.compile("retail-price", re.I))
    if price_tag:
        cena_brutto_pln = _to_int_pl(price_tag.get_text())
    else:
        # js--priceGrossFormatted bywa pustym placeholderem wypelnianym JS-em
        gross_tag = soup.find(class_="js--priceGrossFormatted")
        if gross_tag:
            cena_brutto_pln = _to_int_pl(gross_tag.get_text())
        if cena_brutto_pln is None:
            fallback_tag = soup.find(class_=re.compile("price|amount", re.I))
            if fallback_tag:
                cena_brutto_pln = _to_int_pl(fallback_tag.get_text())

    installment_tag = soup.find(class_=re.compile("installment-price", re.I))
    if installment_tag:
        rata_kredytu_pln_mies = _to_int_pl(installment_tag.get_text())

    # Dane techniczne
    tech_specs = extract_tech_specs(soup)
    
    rocznik = _to_int_pl(tech_specs.get("Rok produkcji"))
    przebieg_km = _to_int_pl(tech_specs.get("Przebieg"))
    pojemnosc_cm3 = _to_int_pl(tech_specs.get("Pojemność silnika") or tech_specs.get("Pojemność"))
    moc_km = _to_int_pl(tech_specs.get("Moc"))
    
    # Przetwarzanie liczby drzwi (często jest "5/5" drzwi/miejsc)
    ilosc_drzwi = None
    drzwi_miejsca = tech_specs.get("Liczba drzwi/miejsc")
    if drzwi_miejsca:
        parts = str(drzwi_miejsca).split("/")
        ilosc_drzwi = _to_int_pl(parts[0])

    # Wyposażenie
    eq_groups = extract_equipment_groups(soup)

    # Zdjęcia
    zdjecia_urls = []
    gallery = soup.find("ul", class_="vdp-thumbs")
    if gallery:
        for img in gallery.find_all("img"):
            src = img.get("data-img-src") or img.get("src")
            if src:
                zdjecia_urls.append(urljoin(url, src))
    else:
        # Fallback dla szablonu subdomen dilerskich (ścieżki względne w src)
        gallery = soup.find(class_="vdp__gallery")
        if gallery:
            for img in gallery.find_all("img"):
                src = img.get("data-img-src") or img.get("src")
                if src:
                    zdjecia_urls.append(urljoin(url, src))
    zdjecia_urls = list(dict.fromkeys(zdjecia_urls))

    # Tagi (np. Kraj pochodzenia)
    tagi_oferty = []
    kraj = tech_specs.get("Kraj pochodzenia")
    if kraj:
        tagi_oferty.append(f"Kraj pochodzenia: {kraj}")
    if subtitle_tag_text:
        tagi_oferty.append(subtitle_tag_text)

    # Rodzaj sprzedaży (VAT 23% vs VAT marża)
    rodzaj_sprzedazy = "vat_marza"
    tags_div = soup.find("div", class_="vdp-header__title__tags")
    price_tags_div = soup.find(class_="vdp__offer__price__tags")
    if (tags_div and "VAT 23%" in tags_div.get_text()) or (price_tags_div and "VAT 23%" in price_tags_div.get_text()):
        rodzaj_sprzedazy = "vat_23"

    # Dealer ID (z linku do salonu lub ścieżek obrazków)
    dealer_id = None
    station_link = soup.find("a", href=re.compile(r"/station-id/(\d+)"))
    if station_link:
        m = re.search(r"/station-id/(\d+)", station_link["href"])
        if m:
            dealer_id = m.group(1)
            
    if not dealer_id:
        # Fallback - szukanie w linkach do zdjęć np. /media/Station/218/...
        m = re.search(r"/media/Station/(\d+)/", str(soup))
        if m:
            dealer_id = m.group(1)

    # Pakowanie w strukturę formatu autopunkt.py
    data = {
        "url": url,
        "marka": marka,
        "model": model,
        "wersja": wersja,
        "tytul": tytul,
        "numer_oferty": numer_oferty,
        
        "cena_brutto_pln": cena_brutto_pln,
        "stara_cena_pln": None,
        "najnizsza_cena_30dni_pln": None,
        "korzysc_pln": None,
        "rata_kredytu_pln_mies": rata_kredytu_pln_mies,
        
        "rocznik": rocznik,
        "pierwsza_rejestracja": tech_specs.get("Data pierwszej rejestracji"),
        "vin": tech_specs.get("VIN"),
        "przebieg_km": przebieg_km,
        "typ_nadwozia": tech_specs.get("Rodzaj nadwozia"),
        "typ_silnika": tech_specs.get("Rodzaj paliwa"),
        "pojemnosc_cm3": pojemnosc_cm3,
        "moc_km": moc_km,
        "naped": tech_specs.get("Napęd"),
        "skrzynia_biegow": tech_specs.get("Skrzynia biegów"),
        "kolor": tech_specs.get("Kolor nadwozia"),
        "ilosc_drzwi": ilosc_drzwi,
        
        "dealer_name": dealer_name,
        "dealer_street": dealer_street,
        "dealer_postcode": dealer_postcode,
        "dealer_city": dealer_city,
        "dealer_map_link": dealer_map_link,
        "contact_phone": None,
        "dealer_id": dealer_id,
        
        "rodzaj_sprzedazy": rodzaj_sprzedazy,
        
        "technologia": None,
        "komfort": " | ".join(eq_groups["komfort"]) if eq_groups["komfort"] else None,
        "bezpieczenstwo": " | ".join(eq_groups["bezpieczenstwo"]) if eq_groups["bezpieczenstwo"] else None,
        "wyglad": None,
        "historia": None,
        "finanse": None,
        "wyposazenie_inne": " | ".join(eq_groups["inne"]) if eq_groups["inne"] else None,
        "tagi_oferty": " | ".join(tagi_oferty) if tagi_oferty else None,
        
        "zdjecia": " | ".join(zdjecia_urls) if zdjecia_urls else None,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "pewneauto.pl"
    }

    return data

def main(pages=1, sample_data=True):
    session = requests.Session()
    links = collect_offer_links(session, max_pages=pages)
    
    if sample_data: 
        links = links[:10]
        
    results = []
    for i, url in enumerate(links):
        print(f"[{i+1}/{len(links)}] Pobieram dane z: {url}")
        try:
            res = scrape_offer(session, url)
            if res: results.append(res)
        except Exception as e:
            print(f"  Błąd przy {url}: {e}")
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        # Zapisujemy do CSV w formacie takim jak autopunkt
        output_file = "pewneauto_pelne_dane_format_autopunkt.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"Zapisano {len(df)} ofert do pliku {output_file}")
        
    else:
        print("Nie znaleziono żadnych ofert.")

if __name__ == "__main__":
    main(pages=1, sample_data=True)
