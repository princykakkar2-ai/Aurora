"""
backend/database.py
-------------------
Database configuration and session management for the Drug Interaction Graph Explorer.

Responsibilities:
  1. Loads configuration from .env using python-dotenv.
  2. Reads and validates DATABASE_URL.
  3. Initializes the SQLAlchemy engine and thread-safe session factory (SessionLocal).
  4. Provides declarative Base for database models.
  5. Exposes a reusable FastAPI dependency (get_db) yielding database sessions.
"""

import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# 1. Locate and load the .env file from the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# 2. Retrieve DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")


def get_database_url() -> str:
    """
    Validates that DATABASE_URL is configured, raising a clear and helpful
    error message for beginners if it is missing.
    """
    url = os.getenv("DATABASE_URL")
    if not url or url.strip() == "":
        raise RuntimeError(
            "\n" + "=" * 70 + "\n"
            "[CONFIGURATION ERROR] DATABASE_URL is missing!\n"
            "Please create a '.env' file in your project root with your PostgreSQL credentials:\n\n"
            "  DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/drug_graph\n\n"
            "You can copy '.env.example' to '.env' and edit it with your database details.\n"
            + "=" * 70
        )
    return url.strip()


# Determine engine arguments based on the dialect
def create_app_engine(database_url: str):
    """
    Creates an SQLAlchemy engine with optimal settings:
      - pool_pre_ping=True: Tests connections before using them to prevent stale connection errors.
      - SQLite check_same_thread=False: Needed when running automated tests in SQLite.
    """
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


# Lazy initialization: create engine if DATABASE_URL is present, or defer if not yet configured
engine = None
SessionLocal = None

try:
    _url = get_database_url()
    engine = create_app_engine(_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except RuntimeError:
    # Allows models and schemas to be imported even before .env is configured
    pass

# Declarative base class for all SQLAlchemy ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides an isolated database session per request.
    Automatically closes the session after the request finishes (even if errors occur).
    """
    global engine, SessionLocal
    if SessionLocal is None:
        _url = get_database_url()
        engine = create_app_engine(_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
