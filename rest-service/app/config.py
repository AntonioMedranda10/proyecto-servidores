import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/uleam_reservas")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-09f26e402edf8c5d56c0")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    WEBSOCKET_SERVICE_URL: str = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:3001")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
