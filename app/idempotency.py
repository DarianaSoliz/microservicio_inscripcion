"""
Idempotency Implementation
Ensures operations can be safely retried without side effects
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

@dataclass
class IdempotencyResult:
    key: str
    cached: bool
    result: Any
    timestamp: float

class IdempotencyManager:
    """Manages idempotency using Redis as cache"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        self.ttl = ttl
        self._redis_client: Optional[redis.Redis] = None
        self._cache: Dict[str, Any] = {}  # Fallback in-memory cache
        
        if REDIS_AVAILABLE:
            try:
                self._redis_client = redis.from_url(redis_url) if redis_url else None
            except Exception:
                self._redis_client = None

    async def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result by key"""
        if self._redis_client:
            try:
                cached_data = await self._redis_client.get(f"idempotency:{key}")
                if cached_data:
                    return json.loads(cached_data)
            except Exception:
                pass
        
        # Fallback to in-memory cache
        return self._cache.get(key)

    async def cache_result(self, key: str, result: Any) -> None:
        """Cache result with TTL"""
        serialized_result = json.dumps(result, default=str)
        
        if self._redis_client:
            try:
                await self._redis_client.setex(
                    f"idempotency:{key}",
                    self.ttl,
                    serialized_result
                )
                return
            except Exception:
                pass
        
        # Fallback to in-memory cache
        self._cache[key] = result
        # Simple cleanup for in-memory cache
        if len(self._cache) > 1000:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self._cache.keys())[:100]
            for k in keys_to_remove:
                del self._cache[k]

    def invalidate_cache_entry(self, key: str) -> bool:
        """Invalidate specific cache entry"""
        found = False
        
        if self._redis_client:
            try:
                # This is sync version, in real implementation use async
                result = self._redis_client.delete(f"idempotency:{key}")
                found = result > 0
            except Exception:
                pass
        
        if key in self._cache:
            del self._cache[key]
            found = True
            
        return found

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "backend": "redis" if self._redis_client else "memory",
            "memory_cache_size": len(self._cache)
        }
        
        if self._redis_client:
            try:
                # In real implementation, get Redis stats
                stats["redis_connected"] = True
            except Exception:
                stats["redis_connected"] = False
        
        return stats

class InscriptionIdempotency:
    """Idempotency specifically for inscription operations"""
    
    def __init__(self, manager: Optional[IdempotencyManager] = None):
        self.manager = manager or idempotency_manager

    def generate_key(self, inscription_data: Dict[str, Any]) -> str:
        """Generate idempotency key for inscription data"""
        # Create hash from relevant inscription data
        key_data = {
            "registro_academico": inscription_data.get("registro_academico"),
            "codigo_periodo": inscription_data.get("codigo_periodo"),
            "grupos": sorted(inscription_data.get("grupos", []))  # Sort for consistency
        }
        
        # Create SHA256 hash
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        
        return f"inscription:{key_hash}"

    async def check_idempotency(self, inscription_data: Dict[str, Any]) -> Optional[Any]:
        """Check if inscription operation is idempotent"""
        key = self.generate_key(inscription_data)
        return await self.manager.get_cached_result(key)

    async def cache_inscription_result(self, inscription_data: Dict[str, Any], result: Any) -> None:
        """Cache inscription operation result"""
        key = self.generate_key(inscription_data)
        await self.manager.cache_result(key, result)

# Global instances
idempotency_manager = IdempotencyManager()
inscription_idempotency = InscriptionIdempotency(idempotency_manager)