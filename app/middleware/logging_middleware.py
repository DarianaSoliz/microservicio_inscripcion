"""
Middleware para logging de requests HTTP.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para loggear información detallada de requests y responses.
    """
    
    def __init__(self, app, skip_paths: list = None):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generar ID único para el request
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Verificar si debemos saltear el logging
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Información del request
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log inicial del request
        logger.info(
            f"Request iniciado: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length")
            }
        )
        
        try:
            # Procesar request
            response = await call_next(request)
            
            # Calcular tiempo de procesamiento
            process_time = time.time() - start_time
            
            # Log del response exitoso
            logger.info(
                f"Request completado: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 4),
                    "response_size": response.headers.get("content-length"),
                    "client_ip": client_ip
                }
            )
            
            # Agregar headers de respuesta
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            
            return response
            
        except Exception as exc:
            # Calcular tiempo hasta el error
            process_time = time.time() - start_time
            
            # Log del error
            logger.error(
                f"Request falló: {request.method} {request.url.path} - {type(exc).__name__}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "process_time": round(process_time, 4),
                    "client_ip": client_ip
                }
            )
            
            # Re-lanzar la excepción para que la manejen los handlers
            raise exc
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Obtiene la IP real del cliente considerando proxies y load balancers.
        """
        # Verificar headers de proxies comunes
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Tomar la primera IP de la lista (IP original del cliente)
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback a la IP directa
        return request.client.host if request.client else "unknown"


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging de eventos de seguridad.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.security_logger = get_logger("app.security")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Detectar patrones sospechosos
        self._check_suspicious_patterns(request)
        
        try:
            response = await call_next(request)
            
            # Log eventos de seguridad basados en el status code
            if response.status_code == 401:
                self._log_authentication_failure(request)
            elif response.status_code == 403:
                self._log_authorization_failure(request)
            elif response.status_code == 429:
                self._log_rate_limit_exceeded(request)
            
            return response
            
        except Exception as exc:
            # Log errores de seguridad
            self.security_logger.warning(
                f"Security exception during request processing",
                extra={
                    "request_id": getattr(request.state, 'request_id', None),
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": self._get_client_ip(request),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)
                }
            )
            raise exc
    
    def _check_suspicious_patterns(self, request: Request):
        """
        Verifica patrones sospechosos en el request.
        """
        path = request.url.path.lower()
        query = str(request.query_params).lower()
        
        # Patrones sospechosos comunes
        suspicious_patterns = [
            "script", "javascript", "vbscript", "onload", "onerror",
            "union", "select", "insert", "update", "delete", "drop",
            "../", "..\\", "/etc/", "cmd.exe", "powershell",
            "<script", "</script", "eval(", "alert("
        ]
        
        for pattern in suspicious_patterns:
            if pattern in path or pattern in query:
                self.security_logger.warning(
                    f"Suspicious pattern detected: {pattern}",
                    extra={
                        "request_id": getattr(request.state, 'request_id', None),
                        "path": request.url.path,
                        "method": request.method,
                        "client_ip": self._get_client_ip(request),
                        "pattern": pattern,
                        "query_params": str(request.query_params)
                    }
                )
    
    def _log_authentication_failure(self, request: Request):
        """Log fallos de autenticación."""
        self.security_logger.warning(
            "Authentication failure",
            extra={
                "request_id": getattr(request.state, 'request_id', None),
                "path": request.url.path,
                "method": request.method,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent")
            }
        )
    
    def _log_authorization_failure(self, request: Request):
        """Log fallos de autorización."""
        self.security_logger.warning(
            "Authorization failure",
            extra={
                "request_id": getattr(request.state, 'request_id', None),
                "path": request.url.path,
                "method": request.method,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent")
            }
        )
    
    def _log_rate_limit_exceeded(self, request: Request):
        """Log cuando se excede el rate limit."""
        self.security_logger.warning(
            "Rate limit exceeded",
            extra={
                "request_id": getattr(request.state, 'request_id', None),
                "path": request.url.path,
                "method": request.method,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent")
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Obtiene la IP real del cliente considerando proxies y load balancers.
        """
        # Verificar headers de proxies comunes
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else "unknown"


class DatabaseLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging específico de operaciones de base de datos.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.db_logger = get_logger("app.database.requests")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Solo loggear endpoints que probablemente interactúen con BD
        db_endpoints = ["/api/", "/inscripciones/", "/periodos/", "/historial/"]
        
        if not any(endpoint in request.url.path for endpoint in db_endpoints):
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            # Log operaciones de BD exitosas
            self.db_logger.info(
                f"Database operation completed: {request.method} {request.url.path}",
                extra={
                    "request_id": getattr(request.state, 'request_id', None),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 4),
                    "likely_db_operation": self._determine_db_operation(request.method, request.url.path)
                }
            )
            
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            
            # Log errores de BD
            self.db_logger.error(
                f"Database operation failed: {request.method} {request.url.path}",
                extra={
                    "request_id": getattr(request.state, 'request_id', None),
                    "method": request.method,
                    "path": request.url.path,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "process_time": round(process_time, 4),
                    "likely_db_operation": self._determine_db_operation(request.method, request.url.path)
                }
            )
            
            raise exc
    
    def _determine_db_operation(self, method: str, path: str) -> str:
        """
        Determina el tipo de operación de BD basado en el método HTTP y la ruta.
        """
        if method == "GET":
            return "READ"
        elif method == "POST":
            return "CREATE"
        elif method == "PUT" or method == "PATCH":
            return "UPDATE"
        elif method == "DELETE":
            return "DELETE"
        else:
            return "UNKNOWN"