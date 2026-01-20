"""
Auto-Scraper - scraper do zbierania ofert z autopunkt.pl
"""
from .url_collector import collect_offer_urls
from .offer_parser import parse_offer

__all__ = ["collect_offer_urls", "parse_offer"]
