import os
from sqlalchemy import Column, Integer, String, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Fetch DATABASE_URL from environment variable, with a default for local SQLite development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/vehicle_tracker.db")

# Conditionally apply connect_args for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

class CarListing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String)
    extracted_at = Column(DateTime)
    source_url = Column(String, unique=True)
    data_points = Column(JSON)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
