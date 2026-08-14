#!/usr/bin/env python3
"""
Dedykowany scraper dla aut dostawczych i ciężarowych z Fiat PGD (fiat.pgd.pl).
Eksportuje pobrane oferty do formatu CSV zgodnego ze schematem Car-Scout.
"""
import sys
import argparse
import asyncio
import csv
import logging
import random
import time
from pathlib import Path
from tqdm import tqdm

from scraper.fiat_pgd import FiatPgdScraper


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('scraper_fiat_pgd.log', encoding='utf-8')
        ]
    )


CAR_SCOUT_COLUMNS = [
    "listing_id", "listing_url", "scraped_at", "make", "model", "version", "vin",
    "price_pln", "price_display", "omnibus_lowest_30d_pln", "omnibus_text",
    "production_year", "mileage_km", "fuel_type", "transmission", "engine_power_hp",
    "registration_number", "first_registration_date", "engine_capacity_cm3", "drive",
    "body_type", "doors", "seats", "color", "paint_type", "dealer_name",
    "dealer_address_line1", "dealer_address_line2", "dealer_address_line3",
    "dealer_google_rating", "dealer_review_count", "dealer_google_link",
    "contact_phone", "primary_image_url", "image_count", "image_urls",
    "equipment_audio_multimedia", "equipment_safety", "equipment_comfort_extras",
    "equipment_other", "additional_info_header", "additional_info_content", "specs_json"
]


async def run_scraper(
    url: str = FiatPgdScraper.DEFAULT_LIST_URL,
    output_path: str = "fiat_pgd_car_scout.csv",
    limit: int | None = None,
    min_delay: float = 0.4,
    max_delay: float = 1.0,
    save_to_db: bool = False,
    use_llm: bool = True,
    llm_model: str = "google/gemini-3.5-flash-lite"
):
    logger = logging.getLogger("fiat_pgd_runner")
    scraper = FiatPgdScraper(use_llm=use_llm, llm_model=llm_model)

    logger.info("=" * 60)
    logger.info(f"KROK 1: Zbieranie URL-i z Fiat PGD ({url})")
    logger.info("=" * 60)

    urls = await scraper.collect_urls(limit=limit, base_url=url)
    if not urls:
        logger.error("Nie znaleziono żadnych ofert na stronie!")
        return

    logger.info(f"Znaleziono {len(urls)} ofert do przetworzenia.")

    logger.info("=" * 60)
    logger.info(f"KROK 2: Pobieranie i parsowanie szczegółów pojazdów (LLM: {use_llm}, Model: {llm_model})")
    logger.info("=" * 60)

    car_scout_rows = []
    full_rows = []
    errors = []

    for item_url in tqdm(urls, desc="Pobieranie ofert Fiat PGD"):
        try:
            parsed_data = scraper.parse_offer(item_url)
            full_rows.append(parsed_data)
            
            cs_row = scraper.to_car_scout_row(parsed_data)
            car_scout_rows.append(cs_row)

            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Błąd podczas parsowania {item_url}: {e}")
            errors.append({"url": item_url, "error": str(e)})

    # Opcjonalny zapis do bazy danych
    if save_to_db and full_rows:
        try:
            import models
            import database
            from datetime import datetime
            
            db = next(database.get_db())
            model_keys = models.Vehicle.__table__.columns.keys()

            for data in full_rows:
                v_url = data["url"]
                vehicle_data = {k: v for k, v in data.items() if k in model_keys}
                vehicle_data["source"] = "fiat.pgd.pl"
                vehicle_data["status"] = "active"

                vehicle = db.query(models.Vehicle).filter(models.Vehicle.url == v_url).first()
                if not vehicle:
                    vehicle = models.Vehicle(**vehicle_data)
                    db.add(vehicle)
                    db.flush()
                else:
                    for k, v in vehicle_data.items():
                        if v is not None and k not in ("id", "url", "created_at", "status"):
                            setattr(vehicle, k, v)

                equipment_json = {
                    "technologia": data.get("equipment_audio_multimedia"),
                    "bezpieczenstwo": data.get("equipment_safety"),
                    "komfort": data.get("equipment_comfort_extras"),
                    "wyglad": data.get("equipment_other"),
                    "additional_info_header": data.get("additional_info_header"),
                    "additional_info_content": data.get("additional_info_content"),
                }

                snapshot = models.VehicleSnapshot(
                    vehicle_id=vehicle.id,
                    price=data.get("cena_brutto_pln") or data.get("cena_netto_pln"),
                    old_price=data.get("stara_cena_pln") or data.get("omnibus_lowest_30d_pln"),
                    mileage=data.get("przebieg_km"),
                    equipment_json=equipment_json,
                    tags=data.get("additional_info_header"),
                    pictures=data.get("zdjecia"),
                    source="fiat.pgd.pl",
                    scraped_at=datetime.now()
                )
                db.add(snapshot)

            db.commit()
            logger.info("Pomyślnie zaktualizowano bazę danych!")
        except Exception as e:
            logger.error(f"Błąd podczas zapisu do bazy danych: {e}")

    # Zapis do CSV Car-Scout
    logger.info("=" * 60)
    logger.info(f"KROK 3: Zapis do pliku CSV ({output_path})")
    logger.info("=" * 60)

    out_file = Path(output_path)
    with open(out_file, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAR_SCOUT_COLUMNS)
        writer.writeheader()
        for row in car_scout_rows:
            writer.writerow(row)

    logger.info(f"Zapisano {len(car_scout_rows)} pojazdów do: {out_file.absolute()}")

    if errors:
        err_file = out_file.with_stem(f"{out_file.stem}_errors")
        with open(err_file, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["url", "error"])
            writer.writeheader()
            for err in errors:
                writer.writerow(err)
        logger.warning(f"Błędy ({len(errors)}) zapisano do: {err_file.absolute()}")

    print("\n" + "=" * 60)
    print(f"PODSUMOWANIE:")
    print(f"Pobranych pojazdów: {len(car_scout_rows)} / {len(urls)}")
    print(f"Plik wyjściowy CSV: {out_file.resolve()}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Scraper Fiat PGD -> Car-Scout CSV")
    parser.add_argument("--url", default=FiatPgdScraper.DEFAULT_LIST_URL, help="URL do listy ofert")
    parser.add_argument("--output", "-o", default="fiat_pgd_car_scout.csv", help="Ścieżka do pliku wynikowego CSV")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Maksymalna liczba ofert do pobrania")
    parser.add_argument("--save-db", action="store_true", help="Zapisz pobrane pojazdy do bazy danych")
    parser.add_argument("--no-llm", action="store_true", help="Wyłącz kategoryzację przez LLM (użyj regułowej)")
    parser.add_argument("--model", default="google/gemini-3.5-flash-lite", help="Model LLM w OpenRouter (np. google/gemini-3.5-flash-lite, deepseek/deepseek-v4-flash-0731, openai/gpt-4o-mini)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Szczegółowe logowanie")

    args = parser.parse_args()
    setup_logging(args.verbose)

    asyncio.run(run_scraper(
        url=args.url,
        output_path=args.output,
        limit=args.limit,
        save_to_db=args.save_db,
        use_llm=not args.no_llm,
        llm_model=args.model
    ))


if __name__ == "__main__":
    main()
