"""
Circuit Breaker Pattern implementation for fault tolerance
"""
import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures detected, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Number of failures to open circuit
    recovery_timeout: int = 60          # Seconds to wait before half-open
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures
    success_threshold: int = 3          # Successful calls needed to close circuit
    timeout: int = 10                   # Operation timeout in seconds


class CircuitBreakerStats:
    def __init__(self):
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self.consecutive_successes = 0
        self.consecutive_failures = 0


class CircuitBreakerException(Exception):
    """Raised when circuit breaker is in OPEN state"""
    def __init__(self, circuit_name: str, last_failure: Optional[str] = None):
        self.circuit_name = circuit_name
        self.last_failure = last_failure
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Last failure: {last_failure or 'Unknown'}"
        )


class CircuitBreaker:
    """
    Circuit Breaker implementation for fault tolerance
    
    Usage:
        # As decorator
        @circuit_breaker(name="database", failure_threshold=3)
        async def database_operation():
            # Database call here
            pass
            
        # As context manager
        async def some_operation():
            cb = CircuitBreaker("external_api")
            async with cb:
                # External API call here
                pass
    """
    
    _instances: Dict[str, 'CircuitBreaker'] = {}
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        
        # Store instance for reuse
        CircuitBreaker._instances[name] = self
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    @classmethod
    def get_or_create(cls, name: str, config: Optional[CircuitBreakerConfig] = None) -> 'CircuitBreaker':
        """Get existing circuit breaker or create new one"""
        if name in cls._instances:
            return cls._instances[name]
        return cls(name, config)
    
    async def __aenter__(self):
        """Context manager entry"""
        await self._check_state()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            await self._on_success()
        elif isinstance(exc_val, self.config.expected_exception):
            await self._on_failure(exc_val)
        return False  # Don't suppress exceptions
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with circuit breaker protection"""
        await self._check_state()
        
        try:
            # Apply timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            await self._on_failure(e)
            raise
        except asyncio.TimeoutError as e:
            timeout_error = Exception(f"Operation timeout after {self.config.timeout}s")
            await self._on_failure(timeout_error)
            raise timeout_error
    
    async def _check_state(self):
        """Check if circuit breaker should allow the call"""
        async with self._lock:
            current_time = time.time()
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (self.stats.last_failure_time and 
                    current_time - self.stats.last_failure_time >= self.config.recovery_timeout):
                    
                    self.state = CircuitState.HALF_OPEN
                    self.stats.consecutive_successes = 0
                    logger.info(f"Circuit breaker '{self.name}' moved to HALF_OPEN")
                else:
                    # Still in OPEN state, reject call
                    raise CircuitBreakerException(
                        self.name, 
                        f"Consecutive failures: {self.stats.consecutive_failures}"
                    )
    
    async def _on_success(self):
        """Handle successful operation"""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    logger.info(f"Circuit breaker '{self.name}' moved to CLOSED")
            
            logger.debug(f"Circuit breaker '{self.name}' recorded success")
    
    async def _on_failure(self, exception: Exception):
        """Handle failed operation"""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            if (self.state == CircuitState.CLOSED and 
                self.stats.consecutive_failures >= self.config.failure_threshold):
                
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' moved to OPEN after "
                    f"{self.stats.consecutive_failures} consecutive failures. "
                    f"Last error: {str(exception)}"
                )
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' moved back to OPEN")
            
            logger.debug(f"Circuit breaker '{self.name}' recorded failure: {str(exception)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "last_failure_time": self.stats.last_failure_time,
            "last_success_time": self.stats.last_success_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            }
        }
    
    async def reset(self):
        """Reset circuit breaker to CLOSED state"""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitBreakerStats()
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")


# Decorator for circuit breaker
def circuit_breaker(
    name: str, 
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: tuple = (Exception,),
    success_threshold: int = 3,
    timeout: int = 10
):
    """
    Decorator to apply circuit breaker pattern to functions
    
    Args:
        name: Unique name for this circuit breaker
        failure_threshold: Number of failures to open circuit
        recovery_timeout: Seconds to wait before trying again
        expected_exception: Tuple of exceptions that count as failures
        success_threshold: Successful calls needed to close circuit
        timeout: Operation timeout in seconds
    """
    def decorator(func):
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold,
            timeout=timeout
        )
        
        cb = CircuitBreaker.get_or_create(name, config)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await cb.call(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(cb.call(func, *args, **kwargs))
            return sync_wrapper
    
    return decorator


# Global circuit breaker registry
class CircuitBreakerRegistry:
    """Registry to manage all circuit breakers"""
    
    @staticmethod
    def get_all_stats() -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: cb.get_stats() 
            for name, cb in CircuitBreaker._instances.items()
        }
    
    @staticmethod
    def get_breaker(name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return CircuitBreaker._instances.get(name)
    
    @staticmethod
    async def reset_all():
        """Reset all circuit breakers"""
        for cb in CircuitBreaker._instances.values():
            await cb.reset()
    
    @staticmethod
    async def reset_breaker(name: str) -> bool:
        """Reset specific circuit breaker"""
        cb = CircuitBreaker._instances.get(name)
        if cb:
            await cb.reset()
            return True
        return False


# Pre-configured circuit breakers for common operations
DATABASE_CIRCUIT_BREAKER = CircuitBreaker.get_or_create(
    "database",
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=(Exception,),
        success_threshold=2,
        timeout=15
    )
)

REDIS_CIRCUIT_BREAKER = CircuitBreaker.get_or_create(
    "redis",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=10,
        expected_exception=(Exception,),
        success_threshold=3,
        timeout=5
    )
)

EXTERNAL_API_CIRCUIT_BREAKER = CircuitBreaker.get_or_create(
    "external_api",
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60,
        expected_exception=(Exception,),
        success_threshold=2,
        timeout=30
    )
)