"""
Enhanced Logging Implementation
Provides structured logging with correlation IDs and performance tracking
"""

import logging
import json
import time
import uuid
from typing import Any, Dict, Optional
from contextvars import ContextVar
from dataclasses import dataclass
import sys

# Context variable for correlation ID
correlation_id_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

@dataclass
class LogContext:
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    operation: Optional[str] = None

class CorrelationManager:
    """Manages correlation IDs for request tracing"""
    
    @staticmethod
    def set_correlation_id(correlation_id: str) -> None:
        """Set correlation ID in context"""
        correlation_id_context.set(correlation_id)
    
    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """Get current correlation ID"""
        return correlation_id_context.get()
    
    @staticmethod
    def generate_correlation_id() -> str:
        """Generate new correlation ID"""
        return f"corr_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def get_or_create_correlation_id() -> str:
        """Get existing or create new correlation ID"""
        correlation_id = correlation_id_context.get()
        if not correlation_id:
            correlation_id = CorrelationManager.generate_correlation_id()
            correlation_id_context.set(correlation_id)
        return correlation_id

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log data
        log_data = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add correlation ID if available
        correlation_id = correlation_id_context.get()
        if correlation_id:
            log_data["correlation_id"] = correlation_id
        
        # Add extra fields from the log record
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str, ensure_ascii=False)

class StructuredLogger:
    """Enhanced logger with structured output and correlation tracking"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Add structured handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message"""
        self._log(logging.DEBUG, message, extra)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log info message"""
        self._log(logging.INFO, message, extra)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message"""
        self._log(logging.WARNING, message, extra)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log error message"""
        self._log(logging.ERROR, message, extra)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message"""
        self._log(logging.CRITICAL, message, extra)
    
    def _log(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Internal logging method"""
        # Create log record with extra data
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            __file__,
            0,
            message,
            (),
            None
        )
        
        # Add extra data
        if extra:
            record.extra = extra
        
        self.logger.handle(record)

class PerformanceLogger:
    """Logger for tracking performance metrics"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def log_performance(
        self,
        operation: str,
        duration: float,
        success: bool = True,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log performance metrics"""
        perf_data = {
            "operation": operation,
            "duration_seconds": duration,
            "success": success,
            "performance_metric": True
        }
        
        if extra:
            perf_data.update(extra)
        
        level = "info" if success else "warning"
        message = f"Operation '{operation}' {'completed' if success else 'failed'} in {duration:.3f}s"
        
        self.logger._log(
            logging.INFO if success else logging.WARNING,
            message,
            perf_data
        )

class AuditLogger:
    """Logger for audit events"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def log_audit_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log audit event"""
        audit_data = {
            "audit_event": True,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "timestamp": time.time()
        }
        
        if user_id:
            audit_data["user_id"] = user_id
        
        if extra:
            audit_data.update(extra)
        
        self.logger.info(f"Audit: {action} on {entity_type} {entity_id}", audit_data)

# Context manager for timing operations
class TimedOperation:
    """Context manager for timing operations with automatic logging"""
    
    def __init__(
        self,
        logger: StructuredLogger,
        operation_name: str,
        extra: Optional[Dict[str, Any]] = None
    ):
        self.logger = logger
        self.operation_name = operation_name
        self.extra = extra or {}
        self.start_time = None
        self.performance_logger = PerformanceLogger(logger)
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"Starting operation: {self.operation_name}", self.extra)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        
        self.performance_logger.log_performance(
            self.operation_name,
            duration,
            success,
            self.extra
        )
        
        if not success:
            self.logger.error(
                f"Operation failed: {self.operation_name}",
                {**self.extra, "error": str(exc_val) if exc_val else "Unknown error"}
            )

# Global logger instances
structured_logger = StructuredLogger("registro_microservicio")
performance_logger = PerformanceLogger(structured_logger)
audit_logger = AuditLogger(structured_logger)