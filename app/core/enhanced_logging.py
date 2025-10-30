"""
Enhanced structured logging system for transaction tracking and debugging
Provides correlation IDs, performance metrics, and comprehensive error tracking
"""
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass, field, asdict
import sys
import traceback
from contextvars import ContextVar

# Context variables for tracking across async operations
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
transaction_id_ctx: ContextVar[Optional[str]] = ContextVar('transaction_id', default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


@dataclass
class LogContext:
    """Structured logging context"""
    correlation_id: str
    transaction_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Performance tracking metrics"""
    operation: str
    duration_ms: float
    cpu_time_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    database_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    external_api_calls: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return asdict(self)


class StructuredLogger:
    """Enhanced structured logger with correlation tracking"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current logging context"""
        context = {
            "timestamp": datetime.now().isoformat(),
            "logger_name": self.name,
            "correlation_id": correlation_id_ctx.get(),
            "transaction_id": transaction_id_ctx.get(),
            "user_id": user_id_ctx.get(),
        }
        
        # Remove None values
        return {k: v for k, v in context.items() if v is not None}
    
    def _format_message(
        self, 
        level: str, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> str:
        """Format structured log message"""
        log_entry = {
            "level": level,
            "message": message,
            **self._get_context()
        }
        
        if extra:
            log_entry.update(extra)
        
        if error:
            log_entry.update({
                "error": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc() if sys.exc_info()[0] else None
                }
            })
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))
    
    def debug(self, message: str, **extra):
        """Debug level logging"""
        self.logger.debug(self._format_message("DEBUG", message, extra))
    
    def info(self, message: str, **extra):
        """Info level logging"""
        self.logger.info(self._format_message("INFO", message, extra))
    
    def warning(self, message: str, **extra):
        """Warning level logging"""
        self.logger.warning(self._format_message("WARNING", message, extra))
    
    def error(self, message: str, error: Optional[Exception] = None, **extra):
        """Error level logging"""
        self.logger.error(self._format_message("ERROR", message, extra, error))
    
    def critical(self, message: str, error: Optional[Exception] = None, **extra):
        """Critical level logging"""
        self.logger.critical(self._format_message("CRITICAL", message, extra, error))
    
    def log_performance(self, metrics: PerformanceMetrics, **extra):
        """Log performance metrics"""
        self.info(
            f"Performance metrics for {metrics.operation}",
            performance=metrics.to_dict(),
            **extra
        )
    
    def log_business_event(
        self, 
        event_type: str, 
        entity_type: str, 
        entity_id: str, 
        action: str,
        **extra
    ):
        """Log business events for audit trail"""
        self.info(
            f"Business event: {event_type}",
            business_event={
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "timestamp": datetime.now().isoformat()
            },
            **extra
        )
    
    def log_database_operation(
        self, 
        operation: str, 
        table: str, 
        duration_ms: float,
        affected_rows: Optional[int] = None,
        **extra
    ):
        """Log database operations"""
        self.debug(
            f"Database operation: {operation}",
            database={
                "operation": operation,
                "table": table,
                "duration_ms": duration_ms,
                "affected_rows": affected_rows
            },
            **extra
        )


class ContextManager:
    """Manages logging context across operations"""
    
    @staticmethod
    def set_correlation_id(correlation_id: str):
        """Set correlation ID for current context"""
        correlation_id_ctx.set(correlation_id)
    
    @staticmethod
    def set_transaction_id(transaction_id: str):
        """Set transaction ID for current context"""
        transaction_id_ctx.set(transaction_id)
    
    @staticmethod
    def set_user_id(user_id: str):
        """Set user ID for current context"""
        user_id_ctx.set(user_id)
    
    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """Get current correlation ID"""
        return correlation_id_ctx.get()
    
    @staticmethod
    def get_transaction_id() -> Optional[str]:
        """Get current transaction ID"""
        return transaction_id_ctx.get()
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get current user ID"""
        return user_id_ctx.get()
    
    @staticmethod
    def clear_context():
        """Clear all context variables"""
        correlation_id_ctx.set(None)
        transaction_id_ctx.set(None)
        user_id_ctx.set(None)


@asynccontextmanager
async def logging_context(
    operation: str,
    user_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    component: Optional[str] = None,
    **metadata
):
    """Context manager for structured logging with automatic setup and cleanup"""
    # Generate IDs if not provided
    correlation_id = correlation_id or str(uuid.uuid4())
    
    # Set context
    original_correlation_id = correlation_id_ctx.get()
    original_transaction_id = transaction_id_ctx.get()
    original_user_id = user_id_ctx.get()
    
    correlation_id_ctx.set(correlation_id)
    if transaction_id:
        transaction_id_ctx.set(transaction_id)
    if user_id:
        user_id_ctx.set(user_id)
    
    logger = StructuredLogger(component or "app")
    start_time = time.time()
    
    logger.info(
        f"Starting operation: {operation}",
        operation=operation,
        component=component,
        **metadata
    )
    
    try:
        yield logger
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Completed operation: {operation}",
            operation=operation,
            component=component,
            duration_ms=duration_ms,
            status="success",
            **metadata
        )
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed operation: {operation}",
            error=e,
            operation=operation,
            component=component,
            duration_ms=duration_ms,
            status="error",
            **metadata
        )
        raise
    
    finally:
        # Restore original context
        correlation_id_ctx.set(original_correlation_id)
        transaction_id_ctx.set(original_transaction_id)
        user_id_ctx.set(original_user_id)


class PerformanceTracker:
    """Tracks performance metrics during operations"""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = time.time()
        self.start_cpu_time = time.process_time()
        self.database_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.external_api_calls = 0
    
    def record_database_query(self):
        """Record a database query"""
        self.database_queries += 1
    
    def record_cache_hit(self):
        """Record a cache hit"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss"""
        self.cache_misses += 1
    
    def record_external_api_call(self):
        """Record an external API call"""
        self.external_api_calls += 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        duration_ms = (time.time() - self.start_time) * 1000
        cpu_time_ms = (time.process_time() - self.start_cpu_time) * 1000
        
        return PerformanceMetrics(
            operation=self.operation,
            duration_ms=duration_ms,
            cpu_time_ms=cpu_time_ms,
            database_queries=self.database_queries,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            external_api_calls=self.external_api_calls
        )


@asynccontextmanager
async def performance_tracking(operation: str):
    """Context manager for performance tracking"""
    tracker = PerformanceTracker(operation)
    
    try:
        yield tracker
    finally:
        metrics = tracker.get_metrics()
        logger = StructuredLogger("performance")
        logger.log_performance(metrics)


class AuditLogger:
    """Specialized logger for audit events"""
    
    def __init__(self):
        self.logger = StructuredLogger("audit")
    
    def log_inscription_created(
        self, 
        codigo_inscripcion: str, 
        registro_academico: str, 
        codigo_periodo: str,
        grupos: List[str]
    ):
        """Log inscription creation event"""
        self.logger.log_business_event(
            event_type="INSCRIPTION_CREATED",
            entity_type="INSCRIPTION",
            entity_id=codigo_inscripcion,
            action="CREATE",
            inscription_data={
                "codigo_inscripcion": codigo_inscripcion,
                "registro_academico": registro_academico,
                "codigo_periodo": codigo_periodo,
                "grupos": grupos,
                "group_count": len(grupos)
            }
        )
    
    def log_inscription_failed(
        self, 
        registro_academico: str, 
        codigo_periodo: str,
        grupos: List[str],
        error: str
    ):
        """Log inscription failure event"""
        self.logger.log_business_event(
            event_type="INSCRIPTION_FAILED",
            entity_type="INSCRIPTION",
            entity_id=f"{registro_academico}_{codigo_periodo}",
            action="CREATE_FAILED",
            inscription_data={
                "registro_academico": registro_academico,
                "codigo_periodo": codigo_periodo,
                "grupos": grupos,
                "error": error
            }
        )
    
    def log_group_added(
        self, 
        codigo_inscripcion: str, 
        codigo_grupo: str,
        registro_academico: str
    ):
        """Log group addition event"""
        self.logger.log_business_event(
            event_type="GROUP_ADDED",
            entity_type="INSCRIPTION_DETAIL",
            entity_id=f"{codigo_inscripcion}_{codigo_grupo}",
            action="ADD_GROUP",
            group_data={
                "codigo_inscripcion": codigo_inscripcion,
                "codigo_grupo": codigo_grupo,
                "registro_academico": registro_academico
            }
        )
    
    def log_saga_started(self, saga_id: str, saga_name: str, steps: List[str]):
        """Log saga transaction start"""
        self.logger.log_business_event(
            event_type="SAGA_STARTED",
            entity_type="SAGA_TRANSACTION",
            entity_id=saga_id,
            action="START",
            saga_data={
                "saga_name": saga_name,
                "steps": steps,
                "step_count": len(steps)
            }
        )
    
    def log_saga_completed(self, saga_id: str, saga_name: str, duration_ms: float):
        """Log saga transaction completion"""
        self.logger.log_business_event(
            event_type="SAGA_COMPLETED",
            entity_type="SAGA_TRANSACTION",
            entity_id=saga_id,
            action="COMPLETE",
            saga_data={
                "saga_name": saga_name,
                "duration_ms": duration_ms
            }
        )
    
    def log_saga_compensated(self, saga_id: str, saga_name: str, failed_step: str):
        """Log saga compensation event"""
        self.logger.log_business_event(
            event_type="SAGA_COMPENSATED",
            entity_type="SAGA_TRANSACTION",
            entity_id=saga_id,
            action="COMPENSATE",
            saga_data={
                "saga_name": saga_name,
                "failed_step": failed_step
            }
        )


# Logging configuration
def configure_logging(
    level: str = "INFO",
    format_type: str = "structured",
    include_traceback: bool = True
):
    """Configure application logging"""
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if format_type == "structured":
        # Use minimal formatter since we handle structure in StructuredLogger
        formatter = logging.Formatter('%(message)s')
    else:
        # Traditional format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Configure specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


# Global instances
audit_logger = AuditLogger()


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


# Decorator for automatic logging
def log_operation(
    operation_name: Optional[str] = None,
    component: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False
):
    """Decorator to automatically log function execution"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            extra = {}
            if log_args:
                extra["args"] = [str(arg) for arg in args]
                extra["kwargs"] = {k: str(v) for k, v in kwargs.items()}
            
            async with logging_context(
                operation=op_name,
                component=component,
                **extra
            ) as logger:
                result = await func(*args, **kwargs)
                
                if log_result:
                    logger.debug("Operation result", result=str(result))
                
                return result
        
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to handle differently
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            logger = get_logger(component or "app")
            
            correlation_id = str(uuid.uuid4())
            ContextManager.set_correlation_id(correlation_id)
            
            extra = {}
            if log_args:
                extra["args"] = [str(arg) for arg in args]
                extra["kwargs"] = {k: str(v) for k, v in kwargs.items()}
            
            logger.info(f"Starting operation: {op_name}", operation=op_name, **extra)
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed operation: {op_name}", operation=op_name)
                
                if log_result:
                    logger.debug("Operation result", result=str(result))
                
                return result
            except Exception as e:
                logger.error(f"Failed operation: {op_name}", error=e, operation=op_name)
                raise
            finally:
                ContextManager.clear_context()
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator