from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Vehicle(Base):
    """Służy jako unikalna tożsamość pojazdu (dane stałe)."""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    vin = Column(String, index=True)
    numer_oferty = Column(String, index=True)
    marka = Column(String, index=True)
    model = Column(String, index=True)
    wersja = Column(String)
    
    # Dane techniczne (zazwyczaj stałe)
    rocznik = Column(Integer, index=True)
    pierwsza_rejestracja = Column(String)
    typ_nadwozia = Column(String, index=True)
    typ_silnika = Column(String, index=True)
    pojemnosc_cm3 = Column(Integer)
    moc_km = Column(Integer)
    naped = Column(String)
    skrzynia_biegow = Column(String)
    kolor = Column(String)
    ilosc_drzwi = Column(String)
    
    # Dealer
    dealer_name = Column(String, index=True)
    dealer_street = Column(String)
    dealer_postcode = Column(String)
    dealer_city = Column(String)
    dealer_map_link = Column(String)
    contact_phone = Column(String)
    dealer_id = Column(String, index=True)
    dealer_group = Column(String, index=True)  # nazwa grupy z ScraperConfig
    
    # Rodzaj sprzedaży
    rodzaj_sprzedazy = Column(String, index=True)
    
    source = Column(String, index=True, default="autopunkt.pl")
    status = Column(String, default="active", index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacja do historii
    snapshots = relationship("VehicleSnapshot", back_populates="vehicle", cascade="all, delete-orphan")

class VehicleSnapshot(Base):
    """Dziennik poszczególnych pobrań danych (dane zmienne)."""
    __tablename__ = "vehicle_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    
    # Dane dynamiczne
    price = Column(Integer)
    old_price = Column(Integer)
    mileage = Column(Integer)
    
    # Wyposażenie i Tagi (jako JSON lub Text)
    equipment_json = Column(JSON) # Przechowujemy wszystkie grupy wyposażenia
    equipment = Column(Text)       # Surowe wyposażenie (dla źródeł bez podziału)
    additional_equipment = Column(Text) # Dodatkowe wyposażenie (surowe)
    tags = Column(Text)
    
    # Zdjecia (mogą się zmieniać)
    pictures = Column(Text)
    
    source = Column(String, index=True, default="autopunkt.pl")
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    vehicle = relationship("Vehicle", back_populates="snapshots")

class ScrapeLog(Base):
    """Historia poszczególnych procesów scrapowania."""
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, index=True)
    marketplace = Column(String, index=True)
    start_time = Column(DateTime, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String) # 'running', 'completed', 'error'
    vehicles_scraped = Column(Integer, default=0)
    total_vehicles_in_db = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class ScraperConfig(Base):
    """Konfiguracje dealerów do automatycznego scrapowania."""
    __tablename__ = "scraper_configs"

    id = Column(Integer, primary_key=True, index=True)
    marketplace = Column(String, index=True) # np. pewneauto, autopunkt
    dealer_name = Column(String)
    base_url = Column(String)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

