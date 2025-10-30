import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_NAME: str = "defaultdb"
    DB_PASSWORD: str = ""
    DB_PORT: str = "5432"
    DB_USER: str = "postgres"
    DATABASE_URL: str = "postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require"
    
    # FastAPI
    APP_NAME: str = "Inscription Microservice"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # CORS
    ALLOWED_ORIGINS: list = ["*"]
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Celery/Redis - Configuración para ejecución local sin Docker
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Queue Management
    MAX_WORKERS: int = 4
    DEFAULT_QUEUE_NAME: str = "inscripciones"
    
    class Config:
        env_file = ".env"

settings = Settings()