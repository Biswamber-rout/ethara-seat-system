"""
Database connection / session management.
Uses SQLite by default (DATABASE_URL env var can override to Postgres).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ethara.db")
   if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
       DATABASE_URL = DATABASE_URL.split("://", 1)[1]
       DATABASE_URL = "postgresql+pg8000://" + DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
