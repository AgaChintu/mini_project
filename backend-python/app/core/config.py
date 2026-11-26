import os
import re
import urllib.parse
from pathlib import Path
from typing import List, Set
from dotenv import load_dotenv

# Base backend directory: ClariQ/backend-python
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Load backend-local .env safely
env_file = BACKEND_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)


class Settings:
    """Centralized Supabase and application configuration settings."""

    APP_NAME: str = "ClariQ API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development").lower()

    # Supabase Configuration
    SUPABASE_URL: str = os.getenv(
        "SUPABASE_URL", "https://xkxpptzhirajzjntkrlb.supabase.co"
    ).rstrip("/")
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv(
        "SUPABASE_PUBLISHABLE_KEY",
        "sb_publishable_VQNuPCj6EPq6BcaGMu3fvg_jIj-9RvJ",
    )
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    SUPABASE_JWKS_URL: str = os.getenv(
        "SUPABASE_JWKS_URL",
        f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
    )
    SUPABASE_STORAGE_BUCKET: str = os.getenv(
        "SUPABASE_STORAGE_BUCKET", "clariq-attachments"
    )

    # Database Configuration (Supabase PostgreSQL via psycopg 3)
    DATABASE_URL_ENV: str = os.getenv("DATABASE_URL", "").strip()
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "false").lower() == "true"

    # Backward compatibility attributes
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "postgres")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # JWT Authentication (ClariQ Custom JWT)
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        os.getenv("SECRET_KEY", "clariq-development-secret-change-this"),
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    FACULTY_REGISTRATION_KEY: str = os.getenv("FACULTY_REGISTRATION_KEY", "CLARIQ-FACULTY-2026")
    ADMIN_LOGIN_ID: str = os.getenv("ADMIN_LOGIN_ID", "admin@clariq.edu")
    ADMIN_INITIAL_PASSWORD: str = os.getenv("ADMIN_INITIAL_PASSWORD", "AdminPass123!")
    ADMIN_INITIAL_NAME: str = os.getenv("ADMIN_INITIAL_NAME", "System Administrator")

    # Groq AI Copilot Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_TIMEOUT_SECONDS: int = int(os.getenv("GROQ_TIMEOUT_SECONDS", "30"))

    # Backward compatibility aliases
    SECRET_KEY: str = JWT_SECRET_KEY
    ALGORITHM: str = JWT_ALGORITHM

    # CORS Configuration
    CORS_ORIGINS_RAW: str = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:8000,http://localhost:8000",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [
            item.strip()
            for item in self.CORS_ORIGINS_RAW.split(",")
            if item.strip()
        ]

    # File Attachment Constraints
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB limit
    ALLOWED_MIME_TYPES: Set[str] = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "application/pdf",
    }
    ALLOWED_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".pdf"}

    # Local fallback upload directory (if Supabase Storage unreachable)
    UPLOAD_DIR: Path = (
        Path(os.getenv("UPLOAD_DIR", str(BACKEND_DIR / "uploads"))).resolve()
    )

    @property
    def database_url(self) -> str:
        """
        Returns normalized SQLAlchemy PostgreSQL connection URL using psycopg 3 driver.
        Accepts postgresql:// or postgres:// and converts to postgresql+psycopg://.
        Safely auto-encodes special characters (such as '@') in the password if unescaped.
        """
        raw_url = self.DATABASE_URL_ENV
        if not raw_url:
            return "postgresql+psycopg://postgres:placeholder@db.xkxpptzhirajzjntkrlb.supabase.co:5432/postgres"

        if raw_url.startswith("postgres://"):
            raw_url = "postgresql+psycopg://" + raw_url[len("postgres://") :]
        elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
            raw_url = "postgresql+psycopg://" + raw_url[len("postgresql://") :]

        # Check for unencoded '@' in password: e.g. postgresql+psycopg://user:pass@word@host:port/db
        prefix, sep, rest = raw_url.partition("://")
        if sep and "@" in rest:
            # If there are multiple '@' signs, the last one separates userinfo from host
            at_parts = rest.rsplit("@", 1)
            if len(at_parts) == 2:
                userinfo, host_part = at_parts
                if ":" in userinfo:
                    username, password = userinfo.split(":", 1)
                    # If password contains unescaped '@' or '%', encode it properly
                    encoded_pw = urllib.parse.quote_plus(urllib.parse.unquote_plus(password))
                    raw_url = f"{prefix}://{username}:{encoded_pw}@{host_part}"

        return raw_url


settings = Settings()
