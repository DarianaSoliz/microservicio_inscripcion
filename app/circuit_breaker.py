"""
Circuit Breaker Pattern Implementation
Provides fault tolerance and prevents cascading failures
"""

import asyncio
import time
from enum import Enum
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
import redis.asyncio as redis
import json

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open" 
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: int = 30

class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig, redis_client: Optional[redis.Redis] = None):
        self.name = name
        self.config = config
        self.redis_client = redis_client
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._success_count = 0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if await self._should_reject():
            raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is open")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _should_reject(self) -> bool:
        """Check if requests should be rejected"""
        state = await self.get_state()
        
        if state == CircuitBreakerState.OPEN:
            if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                await self._transition_to_half_open()
                return False
            return True
        
        return False

    async def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state"""
        if self.redis_client:
            state_data = await self.redis_client.get(f"circuit_breaker:{self.name}")
            if state_data:
                data = json.loads(state_data)
                self._state = CircuitBreakerState(data["state"])
                self._failure_count = data["failure_count"]
                self._last_failure_time = data.get("last_failure_time")
        
        return self._state

    async def _on_success(self):
        """Handle successful execution"""
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                await self._transition_to_closed()
        
        await self._persist_state()

    async def _on_failure(self):
        """Handle failed execution"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            await self._transition_to_open()
        elif self._failure_count >= self.config.failure_threshold:
            await self._transition_to_open()
        
        await self._persist_state()

    async def _transition_to_open(self):
        """Transition to OPEN state"""
        self._state = CircuitBreakerState.OPEN
        self._last_failure_time = time.time()

    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self._state = CircuitBreakerState.HALF_OPEN
        self._success_count = 0

    async def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    async def _persist_state(self):
        """Persist state to Redis"""
        if self.redis_client:
            state_data = {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "last_failure_time": self._last_failure_time,
                "success_count": self._success_count
            }
            await self.redis_client.setex(
                f"circuit_breaker:{self.name}",
                3600,  # 1 hour TTL
                json.dumps(state_data)
            )

    async def reset(self):
        """Manually reset circuit breaker"""
        await self._transition_to_closed()
        await self._persist_state()

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold
            }
        }

class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._redis_client: Optional[redis.Redis] = None

    async def initialize_redis(self, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis connection"""
        try:
            self._redis_client = redis.from_url(redis_url)
            await self._redis_client.ping()
        except Exception:
            self._redis_client = None

    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self._circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig()
            self._circuit_breakers[name] = CircuitBreaker(name, config, self._redis_client)
        
        return self._circuit_breakers[name]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}

    async def reset_circuit_breaker(self, name: str):
        """Reset specific circuit breaker"""
        if name in self._circuit_breakers:
            await self._circuit_breakers[name].reset()

# Global registry
circuit_breaker_registry = CircuitBreakerRegistry()

# Predefined circuit breakers
database_circuit_breaker = circuit_breaker_registry.get_circuit_breaker(
    "database",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
)

# Decorator for easy usage
def circuit_breaker(name: str = None, **config_kwargs):
    """Decorator for applying circuit breaker pattern"""
    def decorator(func):
        nonlocal name
        if name is None:
            name = f"{func.__module__}.{func.__name__}"
        
        config = CircuitBreakerConfig(**config_kwargs)
        cb = circuit_breaker_registry.get_circuit_breaker(name, config)
        
        async def wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)
        
        return wrapper
    return decorator