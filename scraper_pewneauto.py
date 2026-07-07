import re
import time
from datetime import datetime
from urllib.parse import urljoin

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
    offer_urls = set()
    page = 1

    while page <= max_pages:
        url = f"{base_url.rstrip('/')}/oferty/_sort/new?strona={page}"
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
    return data

def extract_equipment_groups(soup):
    eq = {
        "bezpieczenstwo": [],
        "komfort": [],
        "inne": []
    }
    
    eq_section = soup.find("section", class_="vdp-eq")
    if not eq_section:
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
    title_tag = soup.find("h1")
    tytul = title_tag.get_text(strip=True) if title_tag else None
    
    marka, model = None, None
    if tytul:
        parts = tytul.split(maxsplit=1)
        if len(parts) > 0: marka = parts[0]
        if len(parts) > 1: model = parts[1]

    header_title_div = soup.find("div", class_="vdp-header__title")
    if header_title_div:
        strong_tag = header_title_div.find("strong")
        wersja = strong_tag.get_text(strip=True) if strong_tag else None
    else:
        # Fallback
        trim_tag = soup.find(class_=re.compile("subtitle|variant|version", re.I))
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
    elif soup.find(class_=re.compile("price|amount", re.I)):
        cena_brutto_pln = _to_int_pl(soup.find(class_=re.compile("price|amount", re.I)).get_text())

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
                zdjecia_urls.append(src)

    # Tagi (np. Kraj pochodzenia)
    tagi_oferty = []
    kraj = tech_specs.get("Kraj pochodzenia")
    if kraj:
        tagi_oferty.append(f"Kraj pochodzenia: {kraj}")

    # Rodzaj sprzedaży (VAT 23% vs VAT marża)
    rodzaj_sprzedazy = "vat_marza"
    tags_div = soup.find("div", class_="vdp-header__title__tags")
    if tags_div and "VAT 23%" in tags_div.get_text():
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
