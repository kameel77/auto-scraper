# Auto-Scraper Full-Stack 🚀

Kompleksowy system do zbierania ofert samochodów, monitorowania cen i analizy trendów rynkowych.

## 🏗 Architektura
- **Scraper Engine**: Python (Playwright + BeautifulSoup) - głęboka ekstrakcja danych z Nuxt JSON.
- **Backend API**: FastAPI - zarządza procesami, historią i statystykami.
- **Database**: PostgreSQL - przechowuje pełną historię zmian dla każdego VIN.
- **Frontend**: Next.js 14 (App Router) + Tailwind CSS + Shadcn UI - dashboard typu premium.

## ✨ Kluczowe Funkcjonalności
- ✅ **Historia Cen**: Każdy odczyt jest logowany, co pozwala na analizę trendów.
- ✅ **Głęboka Ekstrakcja**: Pobiera VIN, kompletne wyposażenie (pogrupowane) i galerie zdjęć.
- ✅ **Dashboard**: Wizualizacja statystyk i przeglądanie ofert w czasie rzeczywistym.
- ✅ **Multi-Link Support**: Śledzenie ofert z wielu podstron automatycznie.

## 🚀 Plan Rozwoju (Multi-Scraper Roadmap)

Projekt został przygotowany pod łatwą rozbudowę o kolejne serwisy ogłoszeniowe.

### Faza 1: Harmonogramowanie (Wkrótce)
- Integracja z Celery lub prostym Cronem wewnątrz Dockera.
- Automatyczne uruchamianie scrapowania co X godzin/dni.

### Faza 2: Kolejne Serwisy (Wkrótce)
- **OTOMOTO Parser**: Implementacja modułu parsującego strukturę OTOMOTO.
- **OLX Parser**: Obsługa ogłoszeń z OLX.
- **Unified Identity**: Mapowanie tych samych ogłoszeń z różnych serwisów po numerze VIN.

### Faza 3: Analiza i Powiadomienia
- Wykrywanie okazji (cena poniżej średniej rynkowej dla danego modelu).
- Powiadomienia Telegram/Email o nowych ofertach spełniających kryteria.
- Zaawansowane wykresy trendów w dashboardzie.

## 🚀 Konfiguracja Coolify (Step-by-Step)

System został przygotowany do pracy w architekturze kontenerowej zautomatyzowanej przez GitHub Actions.

### 1. GitHub Actions & GHCR
Po wypchnięciu kodu do repozytorium (`git push origin main`), GitHub Actions automatycznie zbuduje i wyśle dwa obrazy do GitHub Container Registry (GHCR):
- `ghcr.io/twoj-user/twoje-repo-backend:latest`
- `ghcr.io/twoj-user/twoje-repo-frontend:latest`

### 2. Przygotowanie Bazy Danych
1. W Coolify przejdź do **Resources** -> **New Resource** -> **Databases** -> **PostgreSQL**.
2. Skonfiguruj bazę i skopiuj **Internal Connection String** (np. `postgresql://user:pass@host:5432/db`).

### 3. Setup Backendu (FastAPI)
1. **New Resource** -> **Applications** -> **Docker Image**.
2. Image: `ghcr.io/twoj-user/twoje-repo-backend:latest`.
3. W zakładce **Environment Variables** dodaj:
   - `DATABASE_URL`: (Connection string z kroku 2).
4. Port: `8000`.

### 4. Setup Frontendu (Next.js)
1. **New Resource** -> **Applications** -> **Docker Image**.
2. Image: `ghcr.io/twoj-user/twoje-repo-frontend:latest`.
3. W zakładce **Environment Variables** dodaj:
   - `NEXT_PUBLIC_API_URL`: Publiczny adres Twojego backendu (np. `https://api.twoja-domena.pl`).
4. Port: `3000`.

## 🛠 Instalacja i Uruchomienie Lokalne

1. Zainstaluj zależności: `pip install -r requirements.txt`
2. Zainstaluj przeglądarki: `playwright install chromium`
3. Uruchom API: `uvicorn api:app --reload`
4. Uruchom Frontend: `cd web && npm install && npm run dev`

## 📂 Struktura Projektu
```
auto-scraper/
├── web/                     # Dashboard (Next.js)
├── scraper/                 # Silnik scrapujący
├── api.py                   # Warstwa API (FastAPI)
├── models.py                # Modele bazy danych (SQLAlchemy)
├── database.py              # Konfiguracja DB
├── Dockerfile               # Konfiguracja kontenera Backend
├── web/Dockerfile           # Konfiguracja kontenera Frontend
├── .github/workflows/       # CI/CD (GitHub Actions)
└── requirements.txt         # Zależności Python
```

---
*Projekt rozwijany z myślą o profesjonalnej analizie rynku automotive.*
