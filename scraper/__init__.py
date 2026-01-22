from .base import BaseScraper
from .autopunkt import AutopunktScraper
from .findcar import FindcarScraper

def get_scraper(name: str) -> BaseScraper:
    """
    Factory function to get a scraper instance by name.
    """
    scrapers = {
        "autopunkt": AutopunktScraper,
        "findcar": FindcarScraper
    }
    
    scraper_class = scrapers.get(name.lower())
    if not scraper_class:
        raise ValueError(f"Unknown marketplace: {name}. Available: {list(scrapers.keys())}")
    
    return scraper_class()

__all__ = ["get_scraper", "BaseScraper", "AutopunktScraper", "FindcarScraper"]
