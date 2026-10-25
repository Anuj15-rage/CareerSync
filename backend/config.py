import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Base directory (CareerSync root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "CareerSync"
    PROJECT_TITLE: str = "Resume-Based Career and Resource Recommendation System"
    API_VERSION: str = "1.0.0"

    # Database parameters
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "careersync_db")
    DB_SSL: bool = os.getenv("DB_SSL", "false").lower() in ("true", "1", "yes")
    DB_SSL_CA: Optional[str] = os.getenv("DB_SSL_CA", None)

    # CORS configuration
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000",
    )

    # Security and proxy trust
    TRUSTED_PROXIES: str = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1")

    # Rate limiting
    RATE_LIMIT_UPLOADS: int = int(os.getenv("RATE_LIMIT_UPLOADS", "5"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))

    # Request size limits (7 MB total request ceiling)
    MAX_REQUEST_SIZE_BYTES: int = int(os.getenv("MAX_REQUEST_SIZE_BYTES", str(7 * 1024 * 1024)))

    # Lifecycle & retention management
    RESUME_EXPIRATION_HOURS: int = int(os.getenv("RESUME_EXPIRATION_HOURS", "24"))
    CLEANUP_INTERVAL_MINUTES: int = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "60"))

    @property
    def cors_origins_list(self) -> list:
        """Parse comma-separated CORS_ORIGINS string into a list."""
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_proxies_set(self) -> set:
        """Parse comma-separated TRUSTED_PROXIES string into a normalized set."""
        if not self.TRUSTED_PROXIES:
            return set()
        return {p.strip().lower() for p in self.TRUSTED_PROXIES.split(",") if p.strip()}

    @property
    def database_url(self) -> str:
        """Construct the SQLAlchemy connection URI."""
        encoded_password = quote_plus(self.DB_PASSWORD) if self.DB_PASSWORD else ""
        user_info = f"{self.DB_USER}:{encoded_password}" if encoded_password else self.DB_USER
        return f"mysql+pymysql://{user_info}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def safe_database_url(self) -> str:
        """Safe representation with masked credentials for logging and health checks."""
        return f"mysql+pymysql://{self.DB_USER}:****@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
