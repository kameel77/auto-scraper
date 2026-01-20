#!/usr/bin/env python3
"""
Main scraper script - orchestrates URL collection and offer parsing
"""
import asyncio
import argparse
import logging
import sys
import time
import random
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from scraper import collect_offer_urls, parse_offer


def setup_logging(verbose: bool = False):
    """Konfiguruje logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('scraper.log', encoding='utf-8')
        ]
    )


async def main():
    """Główna funkcja scrapera."""
    parser = argparse.ArgumentParser(
        description='Scraper ofert samochodów z autopunkt.pl'
    )
    parser.add_argument(
        '--url',
        default='https://autopunkt.pl/znajdz-auto',
        help='URL strony z listą ofert'
    )
    parser.add_argument(
        '--max-scrolls',
        type=int,
        default=60,
        help='Maksymalna liczba scrollów (default: 60)'
    )
    parser.add_argument(
        '--scroll-pause',
        type=float,
        default=1.0,
        help='Pauza między scrollami w sekundach (default: 1.0)'
    )
    parser.add_argument(
        '--output',
        default='autopunkt_vehicles.csv',
        help='Nazwa pliku wyjściowego CSV (default: autopunkt_vehicles.csv)'
    )
    parser.add_argument(
        '--min-delay',
        type=float,
        default=0.8,
        help='Minimalne opóźnienie między requestami w sekundach (default: 0.8)'
    )
    parser.add_argument(
        '--max-delay',
        type=float,
        default=1.8,
        help='Maksymalne opóźnienie między requestami w sekundach (default: 1.8)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit liczby ofert do sparsowania (domyślnie: wszystkie)'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Uruchom przeglądarkę w trybie headless (default: True)'
    )
    parser.add_argument(
        '--no-headless',
        dest='headless',
        action='store_false',
        help='Uruchom przeglądarkę z GUI'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Włącz szczegółowe logowanie'
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    
    # === FAZA 1: Zbieranie URL-i ===
    logger.info("=" * 60)
    logger.info("FAZA 1: Zbieranie URL-i ofert")
    logger.info("=" * 60)
    
    try:
        offer_urls = await collect_offer_urls(
            list_url=args.url,
            max_scroll_rounds=args.max_scrolls,
            scroll_pause=args.scroll_pause,
            headless=args.headless
        )
    except Exception as e:
        logger.error(f"Błąd podczas zbierania URL-i: {e}")
        sys.exit(1)
    
    if not offer_urls:
        logger.warning("Nie znaleziono żadnych URL-i ofert!")
        sys.exit(1)
    
    logger.info(f"Zebrano {len(offer_urls)} URL-i")
    
    # Opcjonalny limit
    if args.limit and args.limit < len(offer_urls):
        logger.info(f"Ograniczam do {args.limit} ofert")
        offer_urls = offer_urls[:args.limit]
    
    # === FAZA 2: Parsowanie ofert ===
    logger.info("=" * 60)
    logger.info("FAZA 2: Parsowanie ofert")
    logger.info("=" * 60)
    
    rows = []
    errors = []
    
    for url in tqdm(offer_urls, desc="Parsowanie ofert"):
        try:
            offer_data = parse_offer(url)
            rows.append(offer_data)
            
            # Rate limiting
            delay = random.uniform(args.min_delay, args.max_delay)
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"Błąd parsowania {url}: {e}")
            errors.append({"url": url, "error": str(e)})
    
    # === FAZA 3: Zapis do CSV ===
    logger.info("=" * 60)
    logger.info("FAZA 3: Zapis wyników")
    logger.info("=" * 60)
    
    if rows:
        df = pd.DataFrame(rows)
        output_path = Path(args.output)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Zapisano {len(df)} ofert do: {output_path.absolute()}")
    else:
        logger.warning("Brak danych do zapisania!")
    
    # Podsumowanie błędów
    if errors:
        logger.warning(f"Wystąpiło {len(errors)} błędów podczas parsowania")
        errors_df = pd.DataFrame(errors)
        errors_path = output_path.with_stem(f"{output_path.stem}_errors")
        errors_df.to_csv(errors_path, index=False, encoding='utf-8-sig')
        logger.info(f"Lista błędów zapisana do: {errors_path.absolute()}")
    
    # Statystyki końcowe
    logger.info("=" * 60)
    logger.info("PODSUMOWANIE")
    logger.info("=" * 60)
    logger.info(f"Zebrane URL-e:      {len(offer_urls)}")
    logger.info(f"Sparsowane oferty:  {len(rows)}")
    logger.info(f"Błędy:              {len(errors)}")
    logger.info(f"Sukces:             {len(rows) / len(offer_urls) * 100:.1f}%")
    
    if rows:
        logger.info(f"\nPodgląd pierwszego rekordu:")
        for key, value in rows[0].items():
            if value and len(str(value)) < 100:
                logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
