# Auto-Scraper — Architektura Deploymentu

## Przegląd

Projekt `auto-scraper` (repo: `kameel77/auto-scraper`) składa się z dwóch osobnych serwisów:

| Serwis    | Obraz GHCR                                    | Tag      | Port | Opis                              |
|-----------|-----------------------------------------------|----------|------|-----------------------------------|
| Backend   | `ghcr.io/kameel77/auto-scraper-backend`       | `main`   | 8000 | FastAPI + Playwright scraper      |
| Frontend  | `ghcr.io/kameel77/auto-scraper-frontend`      | `main`   | 3000 | Next.js dashboard                 |

## Pipeline CI/CD

### GitHub Actions (`.github/workflows/deploy.yml`)

Na każdy push do `main`/`master`:
1. **Logowanie** do GitHub Container Registry (`ghcr.io`)
2. **Build & Push Backend** — buduje z głównego `Dockerfile` i pushuje na `ghcr.io/kameel77/auto-scraper-backend:main` + `:latest`
3. **Build & Push Frontend** — buduje z `web/Dockerfile` i pushuje na `ghcr.io/kameel77/auto-scraper-frontend:main` + `:latest`
   - Przekazywany build-arg: `NEXT_PUBLIC_API_URL` (z GitHub Secrets)

### Coolify

- **URL**: https://cool.izzycars.pl
- **Projekt**: Auto Scraper > production
- **GitHub App**: `careful-curlew-o0sw44w0c4wwk4o` (App ID: 2650184)

Obie aplikacje na Coolify mają `build_pack: "dockerimage"` — **nie budują** z kodu źródłowego, tylko **pullują gotowy obraz** z GHCR.

Konfiguracja frontendu:
- **Nazwa**: `AS-prod-frontend-dkkc8ckwc8kcocwkwcws4wo8`
- **Docker Image**: `ghcr.io/kameel77/auto-scraper-frontend`
- **Docker Image Tag**: `main`
- **Custom Docker Options**: `--cap-add SYS_ADMIN --device=/dev/fuse --security-opt apparmor:unconfined --ulimit nofile=1024:1024 --tmpfs /run:rw,noexec,nosuid,size=65536k --hostname=myapp`

### Autentykacja GHCR

Coolify pulluje obrazy z GHCR przez `docker compose pull` na serwerze. Autentykacja działa przez `docker login ghcr.io` na serwerze Coolify — **NIE** przez globalną sekcję "Docker Registries" (Coolify nie ma takiej). Credentials są przechowywane w `~/.docker/config.json` na serwerze.

Wymagany **GitHub PAT (classic)** ze scope: `read:packages`, `write:packages`.

## Znane Problemy

### Błąd `error from registry: denied`

**Przyczyna (2026-02-19)**: Wygasł GitHub PAT token (classic) o nazwie `GHCR`, który był użyty do `docker login ghcr.io` na serwerze Coolify. Token wygasł dzień wcześniej, powodując `denied` przy pullowaniu obrazów — nawet publicznych (Docker używa cached credentials zamiast anonimowego dostępu).

**Rozwiązanie**:
1. Wygenerować nowy GitHub PAT (classic) ze scope `read:packages` + `write:packages`
   - ⚠️ **Ustaw długi czas wygaśnięcia** (np. 1 rok lub "No expiration"), żeby uniknąć powtórki problemu
2. SSH na serwer Coolify: `ssh root@65.108.252.107`
3. Zalogować się do GHCR: `docker login ghcr.io -u kameel77 -p <NOWY_TOKEN>`
4. Redeploy w Coolify

### ⚠️ Pamiętaj

- Jeśli deployment nagle zacznie dawać `denied` — **sprawdź datę wygaśnięcia PAT** na GitHub → Settings → Developer settings → Personal access tokens
- Pakiety GHCR auto-scrapera są **publiczne**, ale `docker login` credentials mają wyższy priorytet — wygasłe credentials blokują nawet publiczne pulle

## Lokalna Struktura

```
auto-scraper/
├── Dockerfile              # Backend: FastAPI + Playwright (Python)
├── api.py                  # Główny plik API (FastAPI)
├── main.py                 # CLI scraper
├── models.py               # SQLAlchemy models
├── database.py             # DB config (SQLite)
├── requirements.txt        # Python dependencies
├── scraper/                # Scrapers (autopunkt, findcar, vehis)
│   ├── __init__.py
│   ├── base.py
│   ├── autopunkt.py
│   ├── findcar.py
│   ├── vehis.py
│   ├── offer_parser.py
│   └── url_collector.py
├── web/                    # Frontend (Next.js)
│   ├── Dockerfile          # Multi-stage: build → standalone
│   ├── src/
│   │   ├── app/page.tsx    # Dashboard z ExportDropdown
│   │   ├── components/     # ScrapeButton, FilterBar, VehicleRow, ExportDropdown
│   │   └── lib/api.ts      # API client
│   └── ...
├── .github/workflows/
│   └── deploy.yml          # CI/CD → GHCR
└── docs/
    ├── deployment.md       # Ten plik
    └── vehis-implementation-plan.md
```

## Źródła Danych (Scrapers)

| Marketplace | Source value w DB | Scraper class     |
|-------------|-------------------|-------------------|
| Autopunkt   | `autopunkt.pl`    | AutopunktScraper  |
| Findcar     | `findcar.pl`      | FindcarScraper    |
| Vehis       | `vehis`           | VehisScraper      |
