from sqlalchemy import Column, Integer, String, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config import DATABASE_URL, DB_CONNECT_ARGS # Import from config

# Use imported configuration
engine = create_engine(DATABASE_URL, connect_args=DB_CONNECT_ARGS)

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
