import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Link do bazy danych (w Coolify będzie to zmienna środowiskowa DATABASE_URL)
# Jeśli nie podano, używamy SQLite jako fallback do testów lokalnych
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vehicles.db")

# Dostosowanie dla PostgreSQL w Coolify (wymuszenie postgresql:// jeśli trzeba)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # check_same_thread jest potrzebne tylko dla SQLite
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
