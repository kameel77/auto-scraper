# Integracja z API Auto-Scraper

Procedura połączenia aplikacji zewnętrznej (np. **car-scout**) z backendem auto-scrapera.
Dane pochodzą ze scrapowania serwisów: `pewneauto.pl` (w tym subdomeny dealerów Toyoty),
`autopunkt.pl`, `findcar.pl`, `vehis.pl`.

## 1. Adres bazowy (base URL)

API działa pod adresem backendu wdrożonego na Coolify — ten sam, który frontend ma
ustawiony w zmiennej `NEXT_PUBLIC_API_URL` (patrz konfiguracja aplikacji w Coolify).
W przykładach poniżej: `https://<host-api>`.

Szybki test połączenia:

```bash
curl https://<host-api>/
# → {"message": "Auto-Scraper API with Trends is running"}
```

## 2. Pobieranie pojazdów (JSON)

### `GET /api/public/vehicles`

Zwraca listę **aktywnych** ofert (oferty, które zniknęły ze źródła, mają status
`archiwum` i nie są zwracane) z najnowszą ceną i przebiegiem z historii snapshotów.

| Parametr       | Typ    | Opis                                                                 |
|----------------|--------|----------------------------------------------------------------------|
| `source`       | string | Źródło danych, np. `pewneauto.pl`, `autopunkt.pl`, `findcar.pl`, `vehis.pl` |
| `dealer_id`    | string | Numer salonu z serwisu źródłowego (np. `180`)                        |
| `dealer_group` | string | Nazwa grupy dealerskiej zdefiniowana w konfiguratorze (np. `Grupa Sabaj`) |

Wszystkie parametry są opcjonalne i można je łączyć. Wartości ze spacjami należy
URL-encodować (`Grupa%20Sabaj`).

```bash
# Wszystkie auta danej grupy dealerskiej pewneauto:
curl "https://<host-api>/api/public/vehicles?source=pewneauto.pl&dealer_group=Grupa%20Sabaj"

# Konkretny salon po dealer_id:
curl "https://<host-api>/api/public/vehicles?source=pewneauto.pl&dealer_id=180"
```

Przykładowy rekord odpowiedzi:

```json
{
  "id": 123,
  "url": "https://uzywane.grupasabaj.pl/oferta/toyota-corolla-...",
  "marka": "Toyota",
  "model": "Corolla",
  "rocznik": 2021,
  "dealer_name": "Toyota Sabaj",
  "dealer_id": "180",
  "dealer_group": "Grupa Sabaj",
  "rodzaj_sprzedazy": "vat_23",
  "price": 89900,
  "mileage": 45000,
  "pictures": ["https://.../1.jpg", "https://.../2.jpg"]
}
```

`rodzaj_sprzedazy` przyjmuje wartości `vat_23` lub `vat_marza`.

## 3. Lista dostępnych grup dealerskich

### `GET /api/dealer-configs`

Zwraca wpisy z konfiguratora dealerów. Pole `dealer_name` to wartość, której należy
użyć jako `dealer_group` w zapytaniach o pojazdy i eksporty.

```bash
curl "https://<host-api>/api/dealer-configs"
# → [{"id":1,"marketplace":"pewneauto","dealer_name":"Grupa Sabaj",
#     "base_url":"https://uzywane.grupasabaj.pl","is_active":1,"created_at":"..."}]
```

## 4. Eksport CSV

Te same filtry (`source`, `dealer_group`) działają na eksportach:

| Endpoint                        | Zawartość                                                        |
|---------------------------------|------------------------------------------------------------------|
| `GET /export/csv`               | Uproszczony CSV (podstawowe dane + wyposażenie)                  |
| `GET /export/csv/car-scout`     | Pełny format car-scout — tylko oferty z ostatniego pobrania      |
| `GET /export/csv/car-scout/archive` | Format car-scout — wszystkie oferty historyczne (+ kolumna `status`) |

```bash
curl -o oferty.csv \
  "https://<host-api>/export/csv/car-scout?source=pewneauto.pl&dealer_group=Grupa%20Sabaj"
```

Uwaga: `/export/csv/car-scout` pomija rekordy bez ceny, rocznika lub przebiegu
(z wyjątkiem źródła `vehis`) — plik może być krótszy niż lista z JSON API.

## 5. Świeżość danych

- Scrape pewneauto uruchamia się automatycznie **codziennie o 6:00 czasu polskiego**
  (Europe/Warsaw) dla wszystkich aktywnych wpisów z konfiguratora dealerów.
- Można go też uruchomić ręcznie z dashboardu (przycisk „Scrape" → „Pewne Auto / Dealerzy")
  albo przez `POST /scrape?marketplace=pewneauto`.
- Pole `dealer_group` wypełnia się w trakcie scrapowania — oferty pobrane przed
  zdefiniowaniem grupy zostaną dotagowane przy kolejnym scrapie.

## 6. Ograniczenia (stan obecny)

- **Brak autoryzacji** — endpointy publiczne są otwarte; nie publikuj adresu API szerzej.
- **Brak paginacji** na `/api/public/vehicles` — zwracany jest pełny wynik filtra.
  Przy większych wolumenach filtruj po `source`/`dealer_group`.
- Payload JSON jest okrojony względem CSV car-scout (brak VIN, wyposażenia, danych
  technicznych i adresu dealera). Jeśli integracja ich potrzebuje — do rozbudowy.
