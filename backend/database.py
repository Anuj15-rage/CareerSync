from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

# Build engine connection arguments (e.g. SSL for cloud-hosted MySQL like TiDB Cloud / Aiven)
connect_args = {}
if settings.DB_SSL:
    if settings.DB_SSL_CA:
        connect_args["ssl"] = {"ca": settings.DB_SSL_CA}
    else:
        connect_args["ssl"] = {}

# Initialize SQLAlchemy engine with connection pooling and pre-ping
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
)

# Session factory for handling requests
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for future SQLAlchemy ORM models
Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency that provides a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict:
    """
    Verify live MySQL connectivity with a simple SELECT 1 query.
    Returns status and safe diagnostic info without exposing credentials.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                return {
                    "connected": True,
                    "database": settings.DB_NAME,
                    "message": "MySQL connection successful (SELECT 1 verified)",
                }
            return {
                "connected": False,
                "database": settings.DB_NAME,
                "message": "Unexpected response from database verification query",
            }
    except OperationalError as oe:
        # Common MySQL operational errors (e.g., unknown database, bad password, server not running)
        orig_msg = str(oe.orig) if hasattr(oe, "orig") else str(oe)
        # Sanitize any accidental password exposure
        if settings.DB_PASSWORD and settings.DB_PASSWORD in orig_msg:
            orig_msg = orig_msg.replace(settings.DB_PASSWORD, "****")

        # Friendly diagnostic hints
        hint = "Check MySQL service and credentials in .env"
        if "1049" in orig_msg:
            hint = f"Database '{settings.DB_NAME}' does not exist yet. Please create it in MySQL Workbench."
        elif "1045" in orig_msg:
            hint = "Access denied. Verify DB_USER and DB_PASSWORD in .env."
        elif "2003" in orig_msg or "Connection refused" in orig_msg:
            hint = f"Cannot reach MySQL server at {settings.DB_HOST}:{settings.DB_PORT}. Ensure MySQL service is running."

        return {
            "connected": False,
            "database": settings.DB_NAME,
            "error_detail": orig_msg,
            "hint": hint,
        }
    except SQLAlchemyError as se:
        return {
            "connected": False,
            "database": settings.DB_NAME,
            "error_detail": "A database error occurred while connecting.",
            "hint": "Check configuration settings in .env.",
        }
    except Exception as e:
        return {
            "connected": False,
            "database": settings.DB_NAME,
            "error_detail": "An unexpected error occurred.",
            "hint": "Ensure MySQL and Python dependencies are configured properly.",
        }
