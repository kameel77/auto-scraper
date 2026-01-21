from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Generator
import models, database
from pydantic import BaseModel
from datetime import datetime
import asyncio
from scraper.url_collector import collect_offer_urls
from scraper.offer_parser import parse_offer
import logging
import json
import os
import csv
import json
import io
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=database.engine)

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

async def run_scraper_task(limit: Optional[int] = None):
    global scrape_progress
    db = database.SessionLocal()
    try:
        scrape_progress["status"] = "collecting"
        scrape_progress["message"] = "Zbieranie URL-i ofert..."
        scrape_progress["current"] = 0
        scrape_progress["total"] = 0
        
        logger.info("Starting background scrape task with snapshots...")
        urls = await collect_offer_urls()
        
        if limit and limit < len(urls):
            logger.info(f"Ograniczam do {limit} ofert")
            urls = urls[:limit]
        
        scrape_progress["total"] = len(urls)
        scrape_progress["status"] = "scraping"
        
        for i, url in enumerate(urls):
            try:
                scrape_progress["current"] = i + 1
                scrape_progress["message"] = f"Parsowanie oferty {i + 1} z {len(urls)}"
                
                data = parse_offer(url)
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
                
                equipment_json = {
                    "technologia": data.get("technologia"),
                    "komfort": data.get("komfort"),
                    "bezpieczenstwo": data.get("bezpieczenstwo"),
                    "wyglad": data.get("wyglad"),
                }
                
                snapshot = models.VehicleSnapshot(
                    vehicle_id=vehicle.id,
                    price=data.get("cena_brutto_pln"),
                    old_price=data.get("stara_cena_pln"),
                    mileage=data.get("przebieg_km"),
                    equipment_json=equipment_json,
                    tags=data.get("tagi_oferty"),
                    pictures=data.get("zdjecia"),
                    scraped_at=datetime.now()
                )
                db.add(snapshot)
                db.commit()
                logger.info(f"Logged snapshot for: {vehicle.marka} {vehicle.model} (ID: {vehicle.id})")
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                db.rollback()
        
        scrape_progress["status"] = "complete"
        scrape_progress["message"] = f"Zakończono! Zebrano {len(urls)} ofert"
        logger.info("Scrape task finished.")
        
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
async def trigger_scrape(background_tasks: BackgroundTasks, limit: Optional[int] = None):
    global scrape_progress
    scrape_progress = {"status": "idle", "current": 0, "total": 0, "message": ""}
    background_tasks.add_task(run_scraper_task, limit=limit)
    return {"message": f"Historical scrape started in background" + (f" (limit={limit})" if limit else " (all offers)") }

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
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Vehicle)
    if marka:
        query = query.filter(models.Vehicle.marka.ilike(f"%{marka}%"))
    
    vehicles = query.offset(skip).limit(limit).all()
    
    # Map to schema with latest snapshot
    result = []
    for v in vehicles:
        # Get latest snapshot
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
            "latest_image": latest.pictures.split(" | ")[0] if latest and latest.pictures else None,
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
    from sqlalchemy import func
    avg_price = db.query(func.avg(models.VehicleSnapshot.price)).scalar() or 0
    brands = db.query(func.count(func.distinct(models.Vehicle.marka))).scalar() or 0
    return {
        "total_vehicles": total_vehicles,
        "total_snapshots": total_snapshots,
        "avg_price": float(avg_price),
        "unique_brands": brands
    }

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
        main_image = all_pictures.split(" | ")[0] if all_pictures else ""
        other_images = " | ".join(all_pictures.split(" | ")[1:]) if all_pictures else ""
        
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
            
        required_fields = latest.price and v.rocznik and latest.mileage
        if not required_fields:
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
        
        picture_list = all_pictures.split(" | ") if all_pictures else []
        vehicle_photos = [p for p in picture_list if "/uploads_pewne/" in p]
        main_image = vehicle_photos[0] if vehicle_photos else ""
        other_images = " | ".join(vehicle_photos[1:]) if len(vehicle_photos) > 1 else ""
        all_pictures = " | ".join(vehicle_photos)
        
        price_display = f"{latest.price:,} PLN".replace(",", " ") if latest.price else ""
        
        equipment_audio = equipment.get("technologia", [])
        equipment_safety = equipment.get("bezpieczenstwo", [])
        equipment_comfort = equipment.get("komfort", [])
        equipment_other = equipment.get("wyglad", [])
        
        audio_str = "|".join(equipment_audio) if isinstance(equipment_audio, list) else str(equipment_audio or "")
        safety_str = "|".join(equipment_safety) if isinstance(equipment_safety, list) else str(equipment_safety or "")
        comfort_str = "|".join(equipment_comfort) if isinstance(equipment_comfort, list) else str(equipment_comfort or "")
        other_str = "|".join(equipment_other) if isinstance(equipment_other, list) else str(equipment_other or "")
        
        scraped_at = latest.scraped_at.isoformat() if latest.scraped_at else ""
        
        writer.writerow([
            v.numer_oferty or (str(v.id) if v.id else ""),
            v.url or "",
            scraped_at,
            v.marka or "",
            v.model or "",
            v.wersja or "",
            v.vin or "",
            str(latest.price) if latest.price else "",
            price_display,
            str(latest.old_price) if latest.old_price else "",
            "",
            str(v.rocznik) if v.rocznik else "",
            str(latest.mileage) if latest.mileage else "",
            v.typ_silnika or "",
            v.skrzynia_biegow or "",
            str(v.moc_km) if v.moc_km else "",
            "",
            v.pierwsza_rejestracja or "",
            str(v.pojemnosc_cm3) if v.pojemnosc_cm3 else "",
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
            all_pictures,
            audio_str,
            safety_str,
            comfort_str,
            other_str,
            "",
            latest.tags or "",
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
