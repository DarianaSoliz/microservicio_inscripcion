"""
Manejadores globales de excepciones para FastAPI.
"""
import logging
import traceback
from typing import Any, Dict
from datetime import datetime

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

from app.exceptions import (
    InscripcionBaseException, DatabaseException, map_common_exceptions,
    HistorialAcademicoException
)
from app.core.logging import get_logger

# Configurar logger
logger = get_logger(__name__)


async def inscripcion_exception_handler(request: Request, exc: InscripcionBaseException) -> JSONResponse:
    """
    Manejador para excepciones personalizadas del sistema de inscripciones
    """
    logger.error(
        f"InscripcionException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "http_status": exc.http_status,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Manejador para errores de validación de Pydantic/FastAPI
    """
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    logger.warning(
        f"ValidationError: {len(errors)} validation errors",
        extra={
            "errors": errors,
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": f"Errores de validación en {len(errors)} campo(s)",
            "details": {
                "validation_errors": errors,
                "total_errors": len(errors)
            },
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Manejador para errores de SQLAlchemy/Base de datos
    """
    error_message = str(exc)
    
    # Mapear errores específicos de SQLAlchemy
    if isinstance(exc, IntegrityError):
        if "duplicate key" in error_message.lower() or "unique constraint" in error_message.lower():
            error_code = "DUPLICATE_RECORD"
            message = "Ya existe un registro con estos datos"
            http_status = status.HTTP_409_CONFLICT
        elif "foreign key constraint" in error_message.lower():
            error_code = "INVALID_REFERENCE"
            message = "Referencia inválida a registro relacionado"
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif "not null constraint" in error_message.lower():
            error_code = "MISSING_REQUIRED_FIELD"
            message = "Campo requerido faltante"
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            error_code = "INTEGRITY_ERROR"
            message = "Error de integridad en base de datos"
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        error_code = "DATABASE_ERROR"
        message = "Error de base de datos"
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    logger.error(
        f"SQLAlchemyError: {type(exc).__name__} - {error_message}",
        extra={
            "error_type": type(exc).__name__,
            "error_code": error_code,
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    return JSONResponse(
        status_code=http_status,
        content={
            "error": True,
            "error_code": error_code,
            "message": message,
            "details": {
                "database_error": error_message,
                "error_type": type(exc).__name__
            },
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Manejador para excepciones HTTP estándar
    """
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": {},
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Manejador general para excepciones no capturadas
    """
    # Intentar mapear a excepción conocida
    try:
        mapped_exc = map_common_exceptions(exc)
        return await inscripcion_exception_handler(request, mapped_exc)
    except Exception:
        # Si no se puede mapear, manejar como error interno
        pass
    
    # Log completo del error para debugging
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "path": request.url.path,
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Error interno del servidor",
            "details": {
                "error_type": type(exc).__name__,
                "support_message": "Por favor contacte al soporte técnico si el problema persiste"
            },
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


# ===== UTILIDADES PARA LOGGING =====

def log_exception_context(
    exc: Exception,
    context: Dict[str, Any] = None,
    level: str = "error"
) -> None:
    """
    Función utilitaria para logging detallado de excepciones con contexto
    """
    context = context or {}
    
    log_data = {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "context": context
    }
    
    if isinstance(exc, InscripcionBaseException):
        log_data.update({
            "error_code": exc.error_code,
            "http_status": exc.http_status,
            "details": exc.details
        })
    
    getattr(logger, level)(
        f"Exception logged: {type(exc).__name__}",
        extra=log_data
    )


def create_error_response(
    error_code: str,
    message: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    details: Dict[str, Any] = None,
    path: str = None,
    request_id: str = None
) -> Dict[str, Any]:
    """
    Crea una respuesta de error estandarizada
    """
    return {
        "error": True,
        "error_code": error_code,
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
        "path": path,
        "request_id": request_id
    }