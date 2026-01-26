from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, and_, or_, text, inspect
from sqlalchemy.orm import Session
from typing import List, Optional, Generator
import models, database
from pydantic import BaseModel
from datetime import datetime
import asyncio
from scraper import get_scraper
import logging
import json
import os
import csv
import json
import io
import time
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=database.engine)

def apply_migrations():
    """Prosta migracja dodająca brakujące kolumny."""
    try:
        inspector = inspect(database.engine)
        tables = inspector.get_table_names()
        if 'vehicle_snapshots' in tables:
            columns = [c['name'] for c in inspector.get_columns('vehicle_snapshots')]
            with database.engine.connect() as conn:
                if 'equipment' not in columns:
                    logger.info("Dodawanie kolumny 'equipment' do vehicle_snapshots")
                    conn.execute(text("ALTER TABLE vehicle_snapshots ADD COLUMN equipment TEXT"))
                if 'additional_equipment' not in columns:
                    logger.info("Dodawanie kolumny 'additional_equipment' do vehicle_snapshots")
                    conn.execute(text("ALTER TABLE vehicle_snapshots ADD COLUMN additional_equipment TEXT"))
                conn.commit()
    except Exception as e:
        logger.error(f"Błąd podczas migracji: {e}")

apply_migrations()

app = FastAPI(title="Auto-Scraper API")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://*.sslip.io", "https://*.sslip.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scrape_progress = {
    "status": "idle",
    "current": 0,
    "total": 0,
    "message": ""
}

# Pydantic models for API responses
class VehicleSchema(BaseModel):
    id: int
    url: str
    marka: Optional[str]
    model: Optional[str]
    wersja: Optional[str]
    rocznik: Optional[int]
    typ_nadwozia: Optional[str]
    lokalizacja_miasto: Optional[str]
    latest_price: Optional[int]
    latest_mileage: Optional[int]
    latest_image: Optional[str]
    scraped_at: Optional[datetime]
    equipment: Optional[dict] = None

    class Config:
        from_attributes = True

class PriceTrendSchema(BaseModel):
    scraped_at: datetime
    price: int
    mileage: int

class StatsSchema(BaseModel):
    total_vehicles: int
    total_snapshots: int
    avg_price: float
    unique_brands: int

async def run_scraper_task(marketplace: str = "autopunkt", limit: Optional[int] = None):
    global scrape_progress
    db = database.SessionLocal()
    try:
        scrape_progress["status"] = "collecting"
        scrape_progress["message"] = f"Zbieranie URL-i ofert ({marketplace})..."
        scrape_progress["current"] = 0
        scrape_progress["total"] = 0
        
        logger.info(f"Starting background scrape task for {marketplace}...")
        scraper = get_scraper(marketplace)
        
        if marketplace == "autopunkt":
            urls = await scraper.collect_urls(limit=limit)
        elif marketplace == "findcar":
            # Calculate max_pages based on limit:
            # - If limit is None/0, go deep (1000 pages)
            # - If limit is set, calculate pages needed (45 results per page)
            if limit:
                max_pages = (limit // 50) + 1
            else:
                max_pages = 1000
                
            urls = await scraper.collect_urls(max_pages=max_pages)
        else:  # vehis
            if limit:
                max_pages = (limit // 50) + 1
            else:
                max_pages = 1000
            urls = await scraper.collect_urls(max_pages=max_pages, page_size=50)
        
        if limit and limit < len(urls):
            logger.info(f"Ograniczam do {limit} ofert")
            urls = urls[:limit]
        
        scrape_progress["total"] = len(urls)
        scrape_progress["status"] = "scraping"
        
        for i, url in enumerate(urls):
            try:
                scrape_progress["current"] = i + 1
                scrape_progress["message"] = f"Parsowanie oferty {i + 1} z {len(urls)}"
                
                data = scraper.parse_offer(url)
                vehicle = db.query(models.Vehicle).filter(models.Vehicle.url == url).first()
                if not vehicle:
                    model_keys = models.Vehicle.__table__.columns.keys()
                    vehicle_data = {k: v for k, v in data.items() if k in model_keys}
                    vehicle = models.Vehicle(**vehicle_data)
                    db.add(vehicle)
                    db.flush()
                else:
                    if data.get("numer_oferty"):
                        vehicle.numer_oferty = data.get("numer_oferty")
                
                # Normalize equipment for snapshots
                if marketplace == "autopunkt":
                    equipment_json = {
                        "technologia": data.get("technologia"),
                        "komfort": data.get("komfort"),
                        "bezpieczenstwo": data.get("bezpieczenstwo"),
                        "wyglad": data.get("wyglad"),
                    }
                elif marketplace == "findcar":
                    equipment_json = {
                        "technologia": data.get("equipment_audio_multimedia"),
                        "komfort": data.get("equipment_comfort_extras"),
                        "bezpieczenstwo": data.get("equipment_safety"),
                        "wyglad": data.get("equipment_other"),
                        "additional_info_header": data.get("additional_info_header"),
                        "additional_info_content": data.get("additional_info_content"),
                    }
                else:  # vehis
                    equipment_json = {
                        "technologia": data.get("equipment_audio_multimedia"),
                        "komfort": data.get("equipment_comfort_extras"),
                        "bezpieczenstwo": data.get("equipment_safety"),
                        "wyglad": data.get("equipment_other"),
                        "additional_info_content": data.get("additional_info_content"),
                    }
                
                snapshot = models.VehicleSnapshot(
                    vehicle_id=vehicle.id,
                    price=data.get("cena_brutto_pln"),
                    old_price=data.get("stara_cena_pln") or data.get("omnibus_lowest_30d_pln"),
                    mileage=data.get("przebieg_km"),
                    equipment_json=equipment_json,
                    equipment=data.get("equipment"),
                    additional_equipment=data.get("additional_equipment"),
                    tags=data.get("tagi_oferty") or data.get("additional_info_header"),
                    pictures=data.get("zdjecia"),
                    source=data.get("source", "autopunkt.pl"),
                    scraped_at=datetime.now()
                )
                db.add(snapshot)
                db.commit()
                logger.info(f"Logged snapshot for: {vehicle.marka} {vehicle.model} (ID: {vehicle.id}) from {marketplace}")
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                db.rollback()
        
        scrape_progress["status"] = "complete"
        scrape_progress["message"] = f"Zakończono! Zebrano {len(urls)} ofert z {marketplace}"
        logger.info(f"Scrape task for {marketplace} finished.")
        
    except Exception as e:
        scrape_progress["status"] = "error"
        scrape_progress["message"] = f"Błąd: {str(e)}"
        logger.error(f"Scrape task error: {e}")
    finally:
        db.close()

# API Endpoints
@app.get("/")
def read_root():
    return {"message": "Auto-Scraper API with Trends is running"}

@app.post("/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, marketplace: str = "autopunkt", limit: Optional[int] = None):
    global scrape_progress
    scrape_progress = {"status": "idle", "current": 0, "total": 0, "message": ""}
    background_tasks.add_task(run_scraper_task, marketplace=marketplace, limit=limit)
    return {"message": f"Scrape for {marketplace} started in background" + (f" (limit={limit})" if limit else "") }

def generate_progress() -> Generator[str, None, None]:
    global scrape_progress
    while True:
        data = json.dumps({
            "status": scrape_progress["status"],
            "message": scrape_progress["message"],
            "current": scrape_progress["current"],
            "total": scrape_progress["total"],
            "collected": scrape_progress.get("collected", scrape_progress["current"])
        })
        yield f"data: {data}\n\n"
        if scrape_progress["status"] in ("complete", "error"):
            break
        time.sleep(0.5)

@app.get("/scrape/progress")
async def scrape_progress_endpoint():
    return StreamingResponse(generate_progress(), media_type="text/event-stream")

@app.get("/vehicles", response_model=List[VehicleSchema])
def get_vehicles(
    skip: int = 0, 
    limit: int = 50, 
    marka: Optional[str] = None,
    model: Optional[str] = None,
    rok_min: Optional[int] = None,
    rok_max: Optional[int] = None,
    cena_min: Optional[int] = None,
    cena_max: Optional[int] = None,
    miasto: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    # Base query for vehicles
    # We join with the latest snapshot for each vehicle to allow filtering by price
    
    # Subquery to get the ID of the latest snapshot for each vehicle
    latest_snapshot_ids = db.query(
        models.VehicleSnapshot.vehicle_id,
        func.max(models.VehicleSnapshot.scraped_at).label('max_scraped_at')
    ).group_by(models.VehicleSnapshot.vehicle_id).subquery()

    latest_snapshots = db.query(models.VehicleSnapshot).join(
        latest_snapshot_ids,
        and_(
            models.VehicleSnapshot.vehicle_id == latest_snapshot_ids.c.vehicle_id,
            models.VehicleSnapshot.scraped_at == latest_snapshot_ids.c.max_scraped_at
        )
    ).subquery()

    query = db.query(models.Vehicle).join(latest_snapshots, models.Vehicle.id == latest_snapshots.c.vehicle_id)

    if marka:
        query = query.filter(models.Vehicle.marka.ilike(f"%{marka}%"))
    if model:
        query = query.filter(models.Vehicle.model.ilike(f"%{model}%"))
    if rok_min:
        query = query.filter(models.Vehicle.rocznik >= rok_min)
    if rok_max:
        query = query.filter(models.Vehicle.rocznik <= rok_max)
    if cena_min:
        query = query.filter(latest_snapshots.c.price >= cena_min)
    if cena_max:
        query = query.filter(latest_snapshots.c.price <= cena_max)
    if miasto:
        query = query.filter(models.Vehicle.dealer_address_line_2.ilike(f"%{miasto}%"))
    
    vehicles = query.offset(skip).limit(limit).all()
    
    # Map to schema
    result = []
    for v in vehicles:
        # Get latest snapshot manually for simplicity in mapping (or we could use the joined data)
        latest = db.query(models.VehicleSnapshot).filter(models.VehicleSnapshot.vehicle_id == v.id).order_by(models.VehicleSnapshot.scraped_at.desc()).first()
        
        v_dict = {
            "id": v.id,
            "url": v.url,
            "marka": v.marka,
            "model": v.model,
            "wersja": v.wersja,
            "rocznik": v.rocznik,
            "typ_nadwozia": v.typ_nadwozia,
            "lokalizacja_miasto": v.dealer_address_line_2.split()[-1] if v.dealer_address_line_2 else None,
            "latest_price": latest.price if latest else None,
            "latest_mileage": latest.mileage if latest else None,
            "latest_image": re.split(r'\s*\|\s*', latest.pictures)[0] if latest and latest.pictures else None,
            "scraped_at": latest.scraped_at if latest else None,
            "equipment": latest.equipment_json if latest else None
        }
        result.append(v_dict)
    return result

@app.get("/vehicles/{vehicle_id}/trends", response_model=List[PriceTrendSchema])
def get_vehicle_trends(vehicle_id: int, db: Session = Depends(database.get_db)):
    snapshots = db.query(models.VehicleSnapshot).filter(models.VehicleSnapshot.vehicle_id == vehicle_id).order_by(models.VehicleSnapshot.scraped_at.asc()).all()
    return [{"scraped_at": s.scraped_at, "price": s.price, "mileage": s.mileage} for s in snapshots]

@app.get("/stats", response_model=StatsSchema)
def get_stats(db: Session = Depends(database.get_db)):
    total_vehicles = db.query(models.Vehicle).count()
    total_snapshots = db.query(models.VehicleSnapshot).count()
    avg_price = db.query(func.avg(models.VehicleSnapshot.price)).scalar() or 0
    brands = db.query(func.count(func.distinct(models.Vehicle.marka))).scalar() or 0
    return {
        "total_vehicles": total_vehicles,
        "total_snapshots": total_snapshots,
        "avg_price": float(avg_price),
        "unique_brands": brands
    }

@app.get("/brands", response_model=List[str])
def get_brands(db: Session = Depends(database.get_db)):
    brands = db.query(models.Vehicle.marka).distinct().filter(models.Vehicle.marka.isnot(None)).order_by(models.Vehicle.marka).all()
    return [b[0] for b in brands]

@app.get("/models", response_model=List[str])
def get_models(marka: Optional[str] = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Vehicle.model).distinct().filter(models.Vehicle.model.isnot(None))
    if marka:
        query = query.filter(models.Vehicle.marka.ilike(f"%{marka}%"))
    models_list = query.order_by(models.Vehicle.model).all()
    return [m[0] for m in models_list]

@app.get("/cities", response_model=List[str])
def get_cities(db: Session = Depends(database.get_db)):
    # Extract cities from dealer_address_line_2
    # This is a bit tricky with SQLite, so we'll do it in Python if needed or just use the column directly
    cities_raw = db.query(models.Vehicle.dealer_address_line_2).distinct().filter(models.Vehicle.dealer_address_line_2.isnot(None)).all()
    
    cities = set()
    for row in cities_raw:
        addr = row[0]
        if addr:
            parts = addr.split()
            if parts:
                cities.add(parts[-1])
    
    return sorted(list(cities))

@app.get("/export/csv")
def export_csv(db: Session = Depends(database.get_db)):
    vehicles = db.query(models.Vehicle).all()
    
    logger.info(f"Exporting {len(vehicles)} vehicles to CSV")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Marka", "Model", "Wersja", "Rok", "Pierwsza rejestracja", "VIN",
        "Paliwo", "Pojemność cm3", "Moc km", "Skrzynia biegów", "Napęd",
        "Typ nadwozia", "Kolor", "Ilość drzwi",
        "Cena", "Przebieg", "Zdjęcie główne", "Pozostałe zdjęcia",
        "Lokalizacja", "URL",
        "Wyposazenie Technologia", "Wyposazenie Komfort", "Wyposazenie Bezpieczenstwo", "Wyposazenie Wyglad"
    ])
    
    for v in vehicles:
        latest = db.query(models.VehicleSnapshot).filter(models.VehicleSnapshot.vehicle_id == v.id).order_by(models.VehicleSnapshot.scraped_at.desc()).first()
        
        raw_equipment = latest.equipment_json if latest else {}
        if isinstance(raw_equipment, str):
            try:
                equipment = json.loads(raw_equipment)
            except:
                equipment = {}
        elif isinstance(raw_equipment, dict):
            equipment = raw_equipment
        else:
            equipment = {}
        
        all_pictures = latest.pictures if latest and latest.pictures else ""
        picture_list = re.split(r'\s*\|\s*', all_pictures) if all_pictures else []
        main_image = picture_list[0] if picture_list else ""
        other_images = " | ".join(picture_list[1:]) if len(picture_list) > 1 else ""
        
        writer.writerow([
            v.id,
            v.marka or "",
            v.model or "",
            v.wersja or "",
            v.rocznik or "",
            v.pierwsza_rejestracja or "",
            v.vin or "",
            v.typ_silnika or "",
            v.pojemnosc_cm3 or "",
            v.moc_km or "",
            v.skrzynia_biegow or "",
            v.naped or "",
            v.typ_nadwozia or "",
            v.kolor or "",
            v.ilosc_drzwi or "",
            latest.price if latest else "",
            latest.mileage if latest else "",
            main_image,
            other_images,
            v.dealer_address_line_2.split()[-1] if v.dealer_address_line_2 else "",
            v.url,
            equipment.get("technologia", "") if equipment else "",
            equipment.get("komfort", "") if equipment else "",
            equipment.get("bezpieczenstwo", "") if equipment else "",
            equipment.get("wyglad", "") if equipment else "",
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vehicles.csv"}
    )

@app.get("/export/csv/car-scout")
def export_car_scout_csv(db: Session = Depends(database.get_db)):
    vehicles = db.query(models.Vehicle).all()
    
    logger.info(f"Exporting {len(vehicles)} vehicles to Car-Scout CSV")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
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
    ])
    
    for v in vehicles:
        if not v.vin and not v.id:
            continue
            
        latest = db.query(models.VehicleSnapshot).filter(
            models.VehicleSnapshot.vehicle_id == v.id
        ).order_by(models.VehicleSnapshot.scraped_at.desc()).first()
        
        if not latest:
            continue
            
        # Relaxed check: allow 0 (e.g. for new cars with 0 mileage)
        has_required = latest.price is not None and v.rocznik is not None and latest.mileage is not None
        if not has_required:
            continue
            
        raw_equipment = latest.equipment_json if latest else {}
        if isinstance(raw_equipment, str):
            try:
                equipment = json.loads(raw_equipment)
            except:
                equipment = {}
        elif isinstance(raw_equipment, dict):
            equipment = raw_equipment
        else:
            equipment = {}
        
        all_pictures = latest.pictures if latest and latest.pictures else ""
        
        picture_list = re.split(r'\s*\|\s*', all_pictures) if all_pictures else []
        
        main_image = picture_list[0] if picture_list else ""
        other_images = " | ".join(picture_list[1:]) if len(picture_list) > 1 else ""
        all_pictures_str = " | ".join(picture_list)
        
        price_display = f"{latest.price:,} PLN".replace(",", " ") if latest.price else ""
        
        equipment_audio = equipment.get("technologia", [])
        equipment_safety = equipment.get("bezpieczenstwo", [])
        equipment_comfort = equipment.get("komfort", [])
        equipment_other = equipment.get("wyglad", [])
        
        # New: Extract additional info for Findcar
        add_info_header = equipment.get("additional_info_header", "")
        add_info_content = equipment.get("additional_info_content", latest.tags if latest else "")
        
        audio_str = "|".join(equipment_audio) if isinstance(equipment_audio, list) else str(equipment_audio or "")
        safety_str = "|".join(equipment_safety) if isinstance(equipment_safety, list) else str(equipment_safety or "")
        comfort_str = "|".join(equipment_comfort) if isinstance(equipment_comfort, list) else str(equipment_comfort or "")
        other_str = "|".join(equipment_other) if isinstance(equipment_other, list) else str(equipment_other or "")
        
        # Priority for raw equipment if available (e.g. for Vehis)
        if latest.equipment:
            audio_str = latest.equipment
        if latest.additional_equipment:
            other_str = latest.additional_equipment
        
        scraped_at = latest.scraped_at.isoformat() if latest.scraped_at else ""
        
        writer.writerow([
            v.numer_oferty or (str(v.id) if v.id else ""),
            v.url or "",
            scraped_at,
            v.marka or "",
            v.model or "",
            v.wersja or "",
            v.vin or "",
            str(latest.price) if latest.price is not None else "",
            price_display,
            str(latest.old_price) if latest.old_price is not None else "",
            "",
            str(v.rocznik) if v.rocznik is not None else "",
            str(latest.mileage) if latest.mileage is not None else "",
            v.typ_silnika or "",
            v.skrzynia_biegow or "",
            str(v.moc_km) if v.moc_km is not None else "",
            "",
            v.pierwsza_rejestracja or "",
            str(v.pojemnosc_cm3) if v.pojemnosc_cm3 is not None else "",
            v.naped or "",
            v.typ_nadwozia or "",
            v.ilosc_drzwi or "",
            "",
            v.kolor or "",
            "",
            v.dealer_name or "",
            v.dealer_address_line_1 or "",
            v.dealer_address_line_2 or "",
            "",
            "",
            "",
            "",
            v.contact_phone or "",
            main_image,
            "",
            all_pictures_str,
            audio_str,
            safety_str,
            comfort_str,
            other_str,
            add_info_header or "",
            add_info_content or "",
            ""
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=car-scout-export.csv"}
    )

@app.post("/admin/reset-db")
def reset_db(background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    background_tasks.add_task(_reset_db_task, db)
    return {"message": "Database reset started"}

def _reset_db_task(db: Session):
    try:
        db.query(models.VehicleSnapshot).delete()
        db.query(models.Vehicle).delete()
        db.commit()
        logger.info("Database cleared successfully")
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        db.rollback()
    finally:
        db.close()
