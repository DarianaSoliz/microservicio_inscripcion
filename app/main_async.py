from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging import configure_uvicorn_logging, get_logger
from app.middleware.logging_middleware import LoggingMiddleware, SecurityLoggingMiddleware, DatabaseLoggingMiddleware
from app.routers import inscripciones, periodos, queue, historial
from app.exceptions import InscripcionBaseException
from app.exception_handlers import (
    inscripcion_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    http_exception_handler,
    general_exception_handler
)

# Configure uvicorn and application logging
configure_uvicorn_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown events"""
    # Startup
    logger.info("🚀 Iniciando microservicio de registro académico...")
    try:
        # Test database connection
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql("SELECT 1"))
            logger.info("✅ Base de datos configurada correctamente")
    except Exception as e:
        logger.error(f"❌ Error configurando base de datos: {e}")
    
    logger.info("✅ Microservicio iniciado correctamente")
    
    yield
    
    # Shutdown
    logger.info("🔄 Cerrando microservicio de registro académico...")
    await engine.dispose()
    logger.info("✅ Microservicio cerrado correctamente")

# Crear aplicación FastAPI con lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Microservicio para la gestión de inscripciones académicas con logging avanzado",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ===== REGISTRAR MIDDLEWARES =====

# Middleware de logging de requests (debe ir al final para capturar todo)
app.add_middleware(
    LoggingMiddleware,
    skip_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
)

# Middleware de seguridad
app.add_middleware(SecurityLoggingMiddleware)

# Middleware para logging de operaciones de BD
app.add_middleware(DatabaseLoggingMiddleware)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== REGISTRAR MANEJADORES DE EXCEPCIONES =====

# Excepciones personalizadas del sistema
app.add_exception_handler(InscripcionBaseException, inscripcion_exception_handler)

# Errores de validación de Pydantic/FastAPI
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Errores de base de datos
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

# Errores HTTP estándar
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# Manejador general para excepciones no capturadas
app.add_exception_handler(Exception, general_exception_handler)

# ===== INCLUIR ROUTERS =====
app.include_router(inscripciones.router, prefix="/api/v1")
app.include_router(periodos.router, prefix="/api/v1")
app.include_router(queue.router, prefix="/api/v1")
app.include_router(historial.router)

@app.get("/")
async def root():
    """Endpoint raíz del microservicio"""
    logger.info("Endpoint raíz consultado")
    return {
        "message": "Microservicio de Registro Académico",
        "version": settings.VERSION,
        "status": "running",
        "mode": "asynchronous",
        "features": [
            "Gestión de inscripciones",
            "Historial académico",
            "Períodos académicos",
            "Cola de tareas asíncronas",
            "Logging avanzado",
            "Manejo de excepciones personalizado"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint con verificación completa"""
    health_logger = get_logger("app.health")
    
    try:
        health_logger.debug("Iniciando health check")
        
        # Verificar conexión a base de datos
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql("SELECT 1"))
            health_logger.debug("Conexión a base de datos verificada")
        
        health_status = {
            "status": "healthy",
            "database": "connected",
            "version": settings.VERSION,
            "mode": "asynchronous",
            "timestamp": "2024-10-28T00:00:00Z",
            "components": {
                "database": "healthy",
                "logging": "operational",
                "middlewares": "operational"
            }
        }
        
        health_logger.info("Health check completado exitosamente")
        return health_status
        
    except Exception as e:
        health_logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy",
                "error": "Service unavailable",
                "components": {
                    "database": "error",
                    "logging": "operational"
                }
            }
        )

@app.get("/metrics")
async def metrics():
    """Endpoint para métricas básicas del sistema"""
    metrics_logger = get_logger("app.metrics")
    
    try:
        # Aquí puedes agregar métricas específicas de tu aplicación
        metrics_data = {
            "uptime": "N/A",  # Implementar cálculo de uptime
            "requests_total": "N/A",  # Implementar contador de requests
            "errors_total": "N/A",  # Implementar contador de errores
            "database_connections": "N/A",  # Implementar métricas de BD
            "mode": "asynchronous"
        }
        
        metrics_logger.debug("Métricas consultadas")
        return metrics_data
        
    except Exception as e:
        metrics_logger.error(f"Error al obtener métricas: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

if __name__ == "__main__":
    import uvicorn
    
    # Log de inicio
    startup_logger = get_logger("app.startup")
    startup_logger.info("🔥 Iniciando servidor de desarrollo...")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config=None,  # Usar nuestro sistema de logging
        access_log=False  # Evitar logs duplicados
    )