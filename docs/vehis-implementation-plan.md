# Vehis provider integration plan

## Swagger analysis (source)

The Vehis API exposes a login endpoint and broker-facing search/subject endpoints for vehicle listings:

- `POST /login` (email/password -> bearer token)
- `GET /broker/subjects` with pagination (`offset`, `limit`) and sorting (`sortBy`, `sortOrder`)
- `GET /broker/subjects/{groupId}/{subjectId}` for detailed vehicle data

Servers:
- https://sandbox-vash.vehistools.pl/api
- https://vash.vehistools.pl/api

## Current architecture touchpoints

- Scraper interface: `BaseScraper.collect_urls()` and `BaseScraper.parse_offer()`.
- Scraper registry: `scraper/__init__.py` (`get_scraper`).
- CLI flow: `main.py`.
- API/background scraping: `api.py`.
- Data schema: `models.py` (`Vehicle`, `VehicleSnapshot`).

## Implementation process

### 1) Authentication

- Use `POST /login` with `email` and `password` form fields.
- Store bearer token for subsequent requests.
- Configure via environment variables:
  - `VEHIS_API_URL` (default: https://vash.vehistools.pl/api)
  - `VEHIS_EMAIL`
  - `VEHIS_PASSWORD`

### 2) URL collection

- Use `GET /broker/subjects` with pagination.
- Build detail URLs as `/broker/subjects/{groupId}/{subjectId}`.
- Return a list of detail URLs for parsing.

### 3) Offer parsing and mapping

Map Vehis fields to internal schema:

- `subject_id` -> `listing_id`, `numer_oferty`
- `brand` -> `marka`
- `model` -> `model`
- `version` -> `wersja`
- `vin` -> `vin`
- `manufacturing_year` -> `rocznik`
- `mileage` -> `przebieg_km`
- `fuel_type` -> `typ_silnika`
- `gearbox_type` -> `skrzynia_biegow`
- `engine_capacity` -> `pojemnosc_cm3`
- `engine_power` -> `moc_km`
- `drive_type` -> `naped`
- `body_type` -> `typ_nadwozia`
- `number_of_doors` -> `ilosc_drzwi`
- `number_of_seats` -> `seats`
- `color` -> `kolor`
- `registration_number` -> `registration_number`
- `first_registration_date` -> `pierwsza_rejestracja`
- `netto_price` or `consumer_netto_price` -> `cena_brutto_pln`
- `equipment` -> `equipment_audio_multimedia`
- `additional_equipment` -> `equipment_other`

### 4) Wiring

- Register `VehisScraper` in `get_scraper`.
- Add `vehis` to CLI marketplace choices.
- Add `vehis` handling to API background task (URL collection + equipment normalization).

### 5) Testing and validation

- Run with a small limit (e.g., `--limit 5`).
- Verify vehicle counts, URL collection, and DB snapshot insertion.
- Validate auth errors (missing token) and pagination.
