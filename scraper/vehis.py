import os
import requests
from datetime import datetime, timezone
from .base import BaseScraper


class VehisScraper(BaseScraper):
    def __init__(self):
        base_url = os.getenv("VEHIS_API_URL", "https://vash.vehistools.pl/api")
        super().__init__(name="vehis", base_url=base_url)
        self.session = self._make_session()
        self._token = None

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "auto-scraper/1.0",
            "Accept": "application/json",
        })
        return session

    def _ensure_auth(self) -> None:
        if self._token:
            return
        email = os.getenv("VEHIS_EMAIL")
        password = os.getenv("VEHIS_PASSWORD")
        if not email or not password:
            raise ValueError("VEHIS_EMAIL i VEHIS_PASSWORD muszą być ustawione dla autoryzacji.")
        response = self.session.post(
            f"{self.base_url}/login",
            data={"email": email, "password": password},
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise ValueError("Brak tokenu w odpowiedzi logowania Vehis.")
        self._token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _safe_int(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value).replace(" ", "").replace(",", ".").split(".")[0])
        except ValueError:
            return None

    def _map_to_pl(self, field: str, value: str) -> str:
        if not value:
            return value
        
        mapping = {
            "fuel_type": {
                "Diesel": "diesel",
                "Petrol unleaded": "benzynowy",
                "Petrol/gas": "benzyna+LPG",
                "Electric": "elektryczny",
                "Hybrid": "hybrydowy",
            },
            "gearbox_type": {
                "Manual gearbox": "manualna",
                "Automatic transmission": "automatyczna",
                "Automatic stepless": "automatyczna",
                "Automatic sequential": "automatyczna",
                "Automated manual gearbox": "półautomatyczna",
            },
            "drive_type": {
                "Front wheel drive": "na przednie koła",
                "Rear wheel drive": "na tylne koła",
                "4 wheel drive permanent": "4x4 (stały)",
                "4 wheel drive general": "4x4",
                "4 wheel drive insertable": "4x4 (dołączany)",
            },
            "body_type": {
                "Sedan": "sedan",
                "Stationwagon": "kombi",
                "Coupe": "coupe",
                "Convertible": "kabriolet",
                "Van": "minivan",
                "SUV": "SUV",
                "Hatchback": "hatchback",
                "Combi": "kombi",
                "Pick-Up": "pick-up",
            }
        }
        
        if field in mapping:
            # Try exact match first, then case-insensitive
            val_map = mapping[field]
            if value in val_map:
                return val_map[value]
            
            for k, v in val_map.items():
                if k.lower() == value.lower():
                    return v
                    
        return value

    def _build_detail_url(self, group_id: str, subject_id: str) -> str:
        return f"{self.base_url}/broker/subjects/{group_id}/{subject_id}"

    async def collect_urls(self, max_pages=10, page_size=50, start_offset=0, **kwargs) -> list[str]:
        self._ensure_auth()
        urls = []
        offset = start_offset
        for _ in range(max_pages):
            params = {
                "offset": offset,
                "limit": page_size,
                "sortBy": "subject_id",
                "sortOrder": "asc",
            }
            response = self.session.get(
                f"{self.base_url}/broker/subjects",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json() or {}
            subjects = payload.get("subjects") or []
            if not subjects:
                break
            for subject in subjects:
                subject_id = subject.get("subject_id")
                group_id = subject.get("group_id")
                if subject_id and group_id:
                    urls.append(self._build_detail_url(group_id, subject_id))
            offset += page_size
        return urls

    def parse_offer(self, url: str) -> dict:
        self._ensure_auth()
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json() or {}
        subjects = payload.get("subjects") or []
        if not subjects:
            raise ValueError(f"Brak danych pojazdu w odpowiedzi Vehis dla {url}")
        data = subjects[0]
        equipment = data.get("equipment") or []
        additional_equipment = data.get("additional_equipment") or []
        images = data.get("images") or []
        if isinstance(images, str):
            images = [img.strip() for img in images.split(",") if img.strip()]

        price_net = data.get("netto_price") or data.get("consumer_netto_price")
        price = self._safe_int(price_net)
        # Convert to Brutto (Net * 1.23) as requested
        price_brutto = int(price * 1.23) if price else None

        return {
            "listing_id": data.get("subject_id"),
            "numer_oferty": data.get("subject_id"),
            "url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "marka": data.get("brand"),
            "model": data.get("model"),
            "wersja": data.get("version"),
            "vin": data.get("vin"),
            "cena_brutto_pln": price_brutto,
            "price_display": f"{price_brutto:,} PLN".replace(",", " ") if price_brutto else None,
            "rocznik": self._safe_int(data.get("manufacturing_year")),
            "przebieg_km": self._safe_int(data.get("mileage")),
            "typ_silnika": self._map_to_pl("fuel_type", data.get("fuel_type")),
            "skrzynia_biegow": self._map_to_pl("gearbox_type", data.get("gearbox_type")),
            "moc_km": self._safe_int(data.get("engine_power")),
            "registration_number": data.get("registration_number"),
            "pierwsza_rejestracja": data.get("first_registration_date"),
            "pojemnosc_cm3": self._safe_int(data.get("engine_capacity")),
            "naped": self._map_to_pl("drive_type", data.get("drive_type")),
            "typ_nadwozia": self._map_to_pl("body_type", data.get("body_type")),
            "ilosc_drzwi": self._safe_int(data.get("number_of_doors")),
            "seats": self._safe_int(data.get("number_of_seats")),
            "kolor": data.get("color"),
            "dealer_name": data.get("dealer_name"),
            "dealer_address_line_1": data.get("location"),
            "primary_image_url": images[0] if images else None,
            "image_count": len(images),
            "zdjecia": "|".join(images),
            "equipment": "|".join(equipment),
            "additional_equipment": "|".join(additional_equipment),
            "equipment_audio_multimedia": "|".join(equipment),
            "equipment_other": "|".join(additional_equipment),
            "additional_info_content": data.get("additional_description"),
            "source": "vehis",
        }
