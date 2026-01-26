from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all marketplace scrapers.
    """
    
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def collect_urls(self, limit: int | None = None, **kwargs) -> list[str]:
        """
        Collect URLs of individual car offers from the marketplace.
        """
        pass

    @abstractmethod
    def parse_offer(self, url: str) -> dict:
        """
        Parse a single offer URL and return a dictionary of car data.
        """
        pass
