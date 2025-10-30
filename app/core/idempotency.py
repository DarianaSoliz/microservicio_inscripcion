"""
Idempotency implementation for inscription system
Ensures that repeated requests with the same idempotency key produce the same result
"""
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict
import redis
import logging

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyResult:
    """Result of an idempotent operation"""
    result: Any
    created_at: datetime
    is_cached: bool = False
    metadata: Optional[Dict[str, Any]] = None


class IdempotencyKeyGenerator:
    """Generates consistent idempotency keys from request data"""
    
    @staticmethod
    def generate_key(
        operation: str,
        user_id: str,
        data: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a deterministic idempotency key from operation parameters
        
        Args:
            operation: The operation name (e.g., "create_inscription")
            user_id: User identifier (registro_academico)
            data: The request data
            additional_context: Additional context for key generation
        
        Returns:
            A deterministic idempotency key
        """
        # Create a normalized representation of the data
        normalized_data = IdempotencyKeyGenerator._normalize_data(data)
        
        # Combine all components
        key_components = {
            "operation": operation,
            "user_id": user_id,
            "data": normalized_data,
            "context": additional_context or {}
        }
        
        # Create JSON string with sorted keys for consistency
        key_string = json.dumps(key_components, sort_keys=True, separators=(',', ':'))
        
        # Generate hash
        hash_object = hashlib.sha256(key_string.encode('utf-8'))
        hash_hex = hash_object.hexdigest()[:16]  # Use first 16 chars
        
        # Format: operation:user_id:hash
        return f"{operation}:{user_id}:{hash_hex}"
    
    @staticmethod
    def _normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize data for consistent key generation"""
        if isinstance(data, dict):
            # Sort lists to ensure consistent ordering
            normalized = {}
            for key, value in data.items():
                if isinstance(value, list):
                    # Sort lists if they contain sortable items
                    try:
                        normalized[key] = sorted(value)
                    except TypeError:
                        # If items are not sortable, keep as is
                        normalized[key] = value
                elif isinstance(value, dict):
                    normalized[key] = IdempotencyKeyGenerator._normalize_data(value)
                else:
                    normalized[key] = value
            return normalized
        return data


class IdempotencyManager:
    """Manages idempotency for operations using Redis as storage"""
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis_client = redis_client
        self.default_ttl = default_ttl  # Default TTL in seconds (1 hour)
        self.key_prefix = "idempotency:"
    
    async def get_or_execute(
        self,
        idempotency_key: str,
        operation_func,
        *args,
        ttl: Optional[int] = None,
        **kwargs
    ) -> IdempotencyResult:
        """
        Get cached result or execute operation if not cached
        
        Args:
            idempotency_key: Unique key for this operation
            operation_func: Function to execute if not cached
            ttl: TTL for cached result (defaults to default_ttl)
            *args, **kwargs: Arguments for operation_func
        
        Returns:
            IdempotencyResult with operation result
        """
        cache_key = f"{self.key_prefix}{idempotency_key}"
        ttl = ttl or self.default_ttl
        
        # Try to get cached result
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                try:
                    cached_result = json.loads(cached_data)
                    logger.info(f"Idempotency cache hit for key: {idempotency_key}")
                    return IdempotencyResult(
                        result=cached_result["result"],
                        created_at=datetime.fromisoformat(cached_result["created_at"]),
                        is_cached=True,
                        metadata=cached_result.get("metadata")
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid cached data for key {idempotency_key}: {e}")
                    # Continue to execute operation
        except Exception as e:
            logger.error(f"Error accessing cache for key {idempotency_key}: {e}")
            # Continue to execute operation
        
        # Execute operation
        logger.info(f"Executing operation for idempotency key: {idempotency_key}")
        try:
            if hasattr(operation_func, '__call__'):
                if hasattr(operation_func, '__await__'):
                    # Async function
                    result = await operation_func(*args, **kwargs)
                else:
                    # Sync function
                    result = operation_func(*args, **kwargs)
            else:
                raise ValueError("operation_func must be callable")
            
            # Cache the result
            cache_data = {
                "result": result,
                "created_at": datetime.now().isoformat(),
                "metadata": {
                    "operation_args_count": len(args),
                    "operation_kwargs_keys": list(kwargs.keys())
                }
            }
            
            try:
                self.redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_data, default=str)
                )
                logger.info(f"Cached result for idempotency key: {idempotency_key}")
            except Exception as e:
                logger.error(f"Error caching result for key {idempotency_key}: {e}")
                # Don't fail the operation just because caching failed
            
            return IdempotencyResult(
                result=result,
                created_at=datetime.now(),
                is_cached=False,
                metadata=cache_data["metadata"]
            )
            
        except Exception as e:
            logger.error(f"Operation failed for idempotency key {idempotency_key}: {e}")
            raise
    
    def invalidate(self, idempotency_key: str) -> bool:
        """
        Invalidate cached result for an idempotency key
        
        Args:
            idempotency_key: Key to invalidate
        
        Returns:
            True if key was found and deleted, False otherwise
        """
        cache_key = f"{self.key_prefix}{idempotency_key}"
        try:
            result = self.redis_client.delete(cache_key)
            if result:
                logger.info(f"Invalidated idempotency cache for key: {idempotency_key}")
            return bool(result)
        except Exception as e:
            logger.error(f"Error invalidating cache for key {idempotency_key}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about idempotency cache"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            
            stats = {
                "total_cached_operations": len(keys),
                "cache_prefix": self.key_prefix,
                "default_ttl": self.default_ttl
            }
            
            # Get some sample keys for debugging
            if keys:
                sample_keys = keys[:5]  # First 5 keys
                stats["sample_keys"] = [key.decode('utf-8') for key in sample_keys]
            
            return stats
        except Exception as e:
            logger.error(f"Error getting idempotency stats: {e}")
            return {"error": str(e)}


class InscriptionIdempotency:
    """Specific idempotency implementation for inscription operations"""
    
    def __init__(self, redis_client: redis.Redis):
        self.manager = IdempotencyManager(redis_client, default_ttl=7200)  # 2 hours
    
    def generate_inscription_key(
        self,
        registro_academico: str,
        codigo_periodo: str,
        grupos: list,
        operation_type: str = "create_inscription"
    ) -> str:
        """Generate idempotency key for inscription operations"""
        data = {
            "codigo_periodo": codigo_periodo,
            "grupos": sorted(grupos),  # Ensure consistent ordering
        }
        
        return IdempotencyKeyGenerator.generate_key(
            operation=operation_type,
            user_id=registro_academico,
            data=data
        )
    
    def generate_group_inscription_key(
        self,
        registro_academico: str,
        codigo_periodo: str,
        grupo: str,
        codigo_inscripcion: Optional[str] = None
    ) -> str:
        """Generate idempotency key for single group inscription"""
        data = {
            "codigo_periodo": codigo_periodo,
            "grupo": grupo,
        }
        
        if codigo_inscripcion:
            data["codigo_inscripcion"] = codigo_inscripcion
        
        return IdempotencyKeyGenerator.generate_key(
            operation="add_group_to_inscription",
            user_id=registro_academico,
            data=data
        )
    
    async def execute_idempotent_inscription(
        self,
        registro_academico: str,
        codigo_periodo: str,
        grupos: list,
        operation_func,
        *args,
        **kwargs
    ) -> IdempotencyResult:
        """Execute inscription with idempotency protection"""
        idempotency_key = self.generate_inscription_key(
            registro_academico, codigo_periodo, grupos
        )
        
        return await self.manager.get_or_execute(
            idempotency_key,
            operation_func,
            *args,
            **kwargs
        )
    
    async def execute_idempotent_group_inscription(
        self,
        registro_academico: str,
        codigo_periodo: str,
        grupo: str,
        operation_func,
        codigo_inscripcion: Optional[str] = None,
        *args,
        **kwargs
    ) -> IdempotencyResult:
        """Execute single group inscription with idempotency protection"""
        idempotency_key = self.generate_group_inscription_key(
            registro_academico, codigo_periodo, grupo, codigo_inscripcion
        )
        
        return await self.manager.get_or_execute(
            idempotency_key,
            operation_func,
            *args,
            **kwargs
        )


# Global idempotency manager instance
_idempotency_manager: Optional[IdempotencyManager] = None
_inscription_idempotency: Optional[InscriptionIdempotency] = None


def get_idempotency_manager(redis_client: redis.Redis) -> IdempotencyManager:
    """Get or create global idempotency manager"""
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager(redis_client)
    return _idempotency_manager


def get_inscription_idempotency(redis_client: redis.Redis) -> InscriptionIdempotency:
    """Get or create global inscription idempotency manager"""
    global _inscription_idempotency
    if _inscription_idempotency is None:
        _inscription_idempotency = InscriptionIdempotency(redis_client)
    return _inscription_idempotency


# Decorator for idempotent operations
def idempotent_operation(
    operation_name: str,
    user_id_param: str = "user_id",
    data_param: str = "data",
    ttl: int = 3600
):
    """
    Decorator to make any operation idempotent
    
    Args:
        operation_name: Name of the operation
        user_id_param: Parameter name that contains user ID
        data_param: Parameter name that contains operation data
        ttl: Cache TTL in seconds
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract parameters for key generation
            user_id = kwargs.get(user_id_param)
            data = kwargs.get(data_param, {})
            
            if not user_id:
                raise ValueError(f"Parameter '{user_id_param}' is required for idempotent operation")
            
            # Generate idempotency key
            idempotency_key = IdempotencyKeyGenerator.generate_key(
                operation=operation_name,
                user_id=user_id,
                data=data
            )
            
            # Get Redis client (this should be injected properly in production)
            from app.routers.queue import redis_client
            manager = get_idempotency_manager(redis_client)
            
            # Execute with idempotency
            return await manager.get_or_execute(
                idempotency_key,
                func,
                *args,
                ttl=ttl,
                **kwargs
            )
        
        return wrapper
    return decorator