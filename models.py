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
    dealer_address_line_1 = Column(String)
    dealer_address_line_2 = Column(String)
    contact_phone = Column(String)
    
    source = Column(String, index=True, default="autopunkt.pl")
    
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
