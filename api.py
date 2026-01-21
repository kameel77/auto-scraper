from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
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
    # Latest snapshot data
    latest_price: Optional[int]
    latest_mileage: Optional[int]
    latest_image: Optional[str]
    scraped_at: Optional[datetime]

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
                
                equipment_json = {
                    "technologia": data.get("wyposazenie_technologia"),
                    "komfort": data.get("wyposazenie_komfort"),
                    "bezpieczenstwo": data.get("wyposazenie_bezpieczenstwo"),
                    "wyglad": data.get("wyposazenie_wyglad"),
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
        asyncio.sleep(0.5)

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
            "scraped_at": latest.scraped_at if latest else None
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
