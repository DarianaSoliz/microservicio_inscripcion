"""
Enhanced queue endpoints with circuit breaker monitoring, saga status, and comprehensive metrics
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import redis
import json
import uuid
from datetime import datetime
from celery import current_app
from celery.result import AsyncResult

from app.core.database_sync import get_db
from app.core.config import settings
from app.core.celery_app import celery_app
from app.core.circuit_breaker import CircuitBreakerRegistry
from app.core.idempotency import get_idempotency_manager, get_inscription_idempotency
from app.core.saga_pattern import get_saga_manager
from app.core.enhanced_logging import get_logger, audit_logger, ContextManager
from app.schemas import InscripcionCreate
from app.tasks_enhanced import (
    create_inscription_task,
    bulk_create_inscriptions_task,
    health_check_task,
    create_single_group_inscription_task,
)

router = APIRouter(prefix="/queue", tags=["Enhanced Queue Management"])
logger = get_logger("queue_endpoints")

# Redis connection for additional features
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Enhanced response models
class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    progress: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    saga_id: Optional[str] = None
    idempotent: Optional[bool] = None


class MultipleTasksResponse(BaseModel):
    main_task_id: str
    group_tasks: List[Dict[str, str]]
    status: str
    message: str
    correlation_id: Optional[str] = None
    total_groups: int
    estimated_duration_minutes: Optional[int] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    current: Optional[int] = None
    total: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    saga_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class QueueStatsResponse(BaseModel):
    active_tasks: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    workers_online: int
    circuit_breakers: Optional[Dict[str, Any]] = None
    saga_transactions: Optional[Dict[str, Any]] = None
    idempotency_cache: Optional[Dict[str, Any]] = None


class CircuitBreakerStatusResponse(BaseModel):
    circuit_breakers: Dict[str, Any]
    overall_health: str
    degraded_services: List[str]


class SagaStatusResponse(BaseModel):
    saga_id: str
    name: str
    status: str
    steps: List[Dict[str, Any]]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class IdempotencyStatsResponse(BaseModel):
    total_cached_operations: int
    cache_hit_rate: Optional[float] = None
    sample_keys: List[str]


# Enhanced endpoints with comprehensive monitoring
@router.post(
    "/inscripciones/async-by-groups",
    response_model=MultipleTasksResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear inscripción con task_id por grupo (Enhanced)",
    description="Versión mejorada con circuit breakers, idempotencia y saga pattern"
)
async def create_inscription_async_by_groups_enhanced(
    inscription_data: InscripcionCreate, 
    db: Session = Depends(get_db)
):
    """Enhanced group-by-group inscription with full fault tolerance"""
    
    correlation_id = str(uuid.uuid4())
    ContextManager.set_correlation_id(correlation_id)
    ContextManager.set_user_id(inscription_data.registro_academico)
    
    try:
        logger.info(
            "Starting enhanced inscription process",
            registro_academico=inscription_data.registro_academico,
            codigo_periodo=inscription_data.codigo_periodo,
            grupos_count=len(inscription_data.grupos),
            correlation_id=correlation_id
        )
        
        # Generate main inscription ID
        main_codigo_inscripcion = (
            f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
        )
        
        # Base data for all tasks
        base_data = {
            "registro_academico": inscription_data.registro_academico,
            "codigo_periodo": inscription_data.codigo_periodo,
            "codigo_inscripcion": main_codigo_inscripcion,
        }
        
        # Create tasks for each group with enhanced error handling
        group_tasks = []
        for grupo in inscription_data.grupos:
            try:
                task = create_single_group_inscription_task.delay(base_data, grupo)
                group_tasks.append({"grupo": grupo, "task_id": task.id})
                
                # Store task metadata in Redis for monitoring
                task_metadata = {
                    "correlation_id": correlation_id,
                    "grupo": grupo,
                    "registro_academico": inscription_data.registro_academico,
                    "created_at": datetime.now().isoformat(),
                    "inscription_type": "single_group"
                }
                redis_client.setex(
                    f"task_metadata:{task.id}",
                    3600,  # 1 hour TTL
                    json.dumps(task_metadata)
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to create task for group {grupo}",
                    error=str(e),
                    correlation_id=correlation_id
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error creating task for group {grupo}: {str(e)}"
                )
        
        # Estimate duration based on group count
        estimated_duration = len(inscription_data.grupos) * 2  # 2 minutes per group
        
        # Log business event
        audit_logger.log_business_event(
            event_type="INSCRIPTION_REQUESTED",
            entity_type="INSCRIPTION",
            entity_id=main_codigo_inscripcion,
            action="CREATE_ASYNC",
            grupos=inscription_data.grupos,
            correlation_id=correlation_id
        )
        
        response = MultipleTasksResponse(
            main_task_id=main_codigo_inscripcion,
            group_tasks=group_tasks,
            status="QUEUED",
            message=f"Inscripción encolada con {len(group_tasks)} tareas (una por grupo)",
            correlation_id=correlation_id,
            total_groups=len(inscription_data.grupos),
            estimated_duration_minutes=estimated_duration
        )
        
        logger.info(
            "Enhanced inscription tasks created successfully",
            main_task_id=main_codigo_inscripcion,
            task_count=len(group_tasks),
            correlation_id=correlation_id
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "Failed to create enhanced inscription tasks",
            error=str(e),
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al encolar tareas: {str(e)}"
        )
    finally:
        ContextManager.clear_context()


@router.post(
    "/tasks/status/multiple",
    response_model=List[TaskStatusResponse],
    summary="Consultar estado de múltiples tareas (Enhanced)",
    description="Versión mejorada con información de saga y correlación"
)
async def get_multiple_tasks_status_enhanced(task_ids: List[str]):
    """Enhanced multiple task status with correlation and saga information"""
    
    correlation_id = str(uuid.uuid4())
    ContextManager.set_correlation_id(correlation_id)
    
    try:
        logger.info(
            "Checking status for multiple tasks",
            task_count=len(task_ids),
            correlation_id=correlation_id
        )
        
        results = []
        for task_id in task_ids:
            try:
                task_result = AsyncResult(task_id, app=celery_app)
                
                # Get task metadata from Redis
                metadata_key = f"task_metadata:{task_id}"
                metadata_json = redis_client.get(metadata_key)
                metadata = {}
                if metadata_json:
                    try:
                        metadata = json.loads(metadata_json)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid metadata JSON for task {task_id}")
                
                response = TaskStatusResponse(
                    task_id=task_id,
                    status=task_result.status,
                    correlation_id=metadata.get("correlation_id"),
                    created_at=metadata.get("created_at")
                )
                
                # Enhanced result handling
                try:
                    if task_result.successful():
                        result_data = task_result.result
                        response.result = result_data
                        response.saga_id = result_data.get("saga_id") if isinstance(result_data, dict) else None
                        response.completed_at = datetime.now().isoformat()
                        
                    elif task_result.failed():
                        exc = task_result.info
                        response.meta = {
                            "error_type": type(exc).__name__ if exc else None,
                            "error_message": str(exc),
                            "retry_count": getattr(task_result, 'retries', 0)
                        }
                        
                    elif task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
                        if isinstance(task_result.info, dict):
                            response.meta = task_result.info
                            response.current = task_result.info.get("current")
                            response.total = task_result.info.get("total")
                        else:
                            response.meta = {
                                "message": f"Task is in {task_result.status} state"
                            }
                            
                except Exception as info_error:
                    response.meta = {
                        "error_type": "TaskInfoError",
                        "error_message": f"Error accessing task info: {str(info_error)}"
                    }
                
                results.append(response)
                
            except Exception as task_error:
                logger.error(
                    f"Error processing task {task_id}",
                    error=str(task_error),
                    correlation_id=correlation_id
                )
                
                results.append(
                    TaskStatusResponse(
                        task_id=task_id,
                        status="ERROR",
                        meta={
                            "error_type": type(task_error).__name__,
                            "error_message": f"Error accessing task: {str(task_error)}"
                        },
                        correlation_id=correlation_id
                    )
                )
        
        logger.info(
            "Multiple task status check completed",
            task_count=len(task_ids),
            successful_checks=len([r for r in results if r.status != "ERROR"]),
            correlation_id=correlation_id
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "Failed to check multiple task status",
            error=str(e),
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar estados: {type(e).__name__}: {str(e)}"
        )
    finally:
        ContextManager.clear_context()


@router.get(
    "/stats/enhanced",
    response_model=QueueStatsResponse,
    summary="Estadísticas completas del sistema",
    description="Incluye circuit breakers, saga transactions e idempotency cache"
)
async def get_enhanced_queue_stats():
    """Get comprehensive system statistics including all resilience patterns"""
    
    correlation_id = str(uuid.uuid4())
    ContextManager.set_correlation_id(correlation_id)
    
    try:
        logger.info("Gathering enhanced system statistics", correlation_id=correlation_id)
        
        # Basic Celery stats
        inspect = celery_app.control.inspect()
        
        active_tasks = inspect.active()
        active_count = sum(len(tasks) for tasks in (active_tasks or {}).values())
        
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()
        
        scheduled_count = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
        reserved_count = sum(len(tasks) for tasks in (reserved_tasks or {}).values())
        pending_count = scheduled_count + reserved_count
        
        stats = inspect.stats()
        workers_online = len(stats or {})
        
        # Redis-based counters
        try:
            completed_tasks = int(redis_client.get("completed_tasks") or 0)
            failed_tasks = int(redis_client.get("failed_tasks") or 0)
        except:
            completed_tasks = 0
            failed_tasks = 0
        
        # Circuit breaker stats
        circuit_breaker_stats = CircuitBreakerRegistry.get_all_stats()
        
        # Saga transaction stats
        saga_manager = get_saga_manager(redis_client)
        saga_stats = {
            "active_sagas": len(saga_manager.active_sagas),
            "total_sagas": len(saga_manager.get_all_sagas_status())
        }
        
        # Idempotency cache stats
        idempotency_manager = get_idempotency_manager(redis_client)
        idempotency_stats = idempotency_manager.get_stats()
        
        response = QueueStatsResponse(
            active_tasks=active_count,
            pending_tasks=pending_count,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            workers_online=workers_online,
            circuit_breakers=circuit_breaker_stats,
            saga_transactions=saga_stats,
            idempotency_cache=idempotency_stats
        )
        
        logger.info(
            "Enhanced statistics gathered successfully",
            active_tasks=active_count,
            workers_online=workers_online,
            circuit_breakers_count=len(circuit_breaker_stats),
            correlation_id=correlation_id
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "Failed to gather enhanced statistics",
            error=str(e),
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas: {str(e)}"
        )
    finally:
        ContextManager.clear_context()


@router.get(
    "/circuit-breakers",
    response_model=CircuitBreakerStatusResponse,
    summary="Estado de circuit breakers",
    description="Monitoreo del estado de todos los circuit breakers"
)
async def get_circuit_breaker_status():
    """Get comprehensive circuit breaker status"""
    
    try:
        circuit_breakers = CircuitBreakerRegistry.get_all_stats()
        
        # Determine overall health
        degraded_services = []
        overall_health = "healthy"
        
        for name, stats in circuit_breakers.items():
            if stats["state"] == "open":
                degraded_services.append(name)
                overall_health = "degraded"
            elif stats["state"] == "half_open":
                overall_health = "recovering" if overall_health == "healthy" else overall_health
        
        return CircuitBreakerStatusResponse(
            circuit_breakers=circuit_breakers,
            overall_health=overall_health,
            degraded_services=degraded_services
        )
        
    except Exception as e:
        logger.error("Failed to get circuit breaker status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado de circuit breakers: {str(e)}"
        )


@router.get(
    "/sagas",
    response_model=List[SagaStatusResponse],
    summary="Estado de transacciones Saga",
    description="Monitoreo de todas las transacciones Saga activas"
)
async def get_saga_transactions():
    """Get status of all saga transactions"""
    
    try:
        saga_manager = get_saga_manager(redis_client)
        saga_statuses = saga_manager.get_all_sagas_status()
        
        responses = []
        for saga_status in saga_statuses:
            responses.append(
                SagaStatusResponse(
                    saga_id=saga_status["transaction_id"],
                    name=saga_status["name"],
                    status=saga_status["status"],
                    steps=saga_status["steps"],
                    created_at=saga_status["created_at"],
                    started_at=saga_status.get("started_at"),
                    completed_at=saga_status.get("completed_at"),
                    error=saga_status.get("error")
                )
            )
        
        return responses
        
    except Exception as e:
        logger.error("Failed to get saga transactions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener transacciones saga: {str(e)}"
        )


@router.get(
    "/idempotency/stats",
    response_model=IdempotencyStatsResponse,
    summary="Estadísticas de cache de idempotencia",
    description="Información sobre el cache de operaciones idempotentes"
)
async def get_idempotency_stats():
    """Get idempotency cache statistics"""
    
    try:
        idempotency_manager = get_idempotency_manager(redis_client)
        stats = idempotency_manager.get_stats()
        
        # Calculate cache hit rate if possible
        cache_hit_rate = None
        # This would require additional metrics collection in production
        
        return IdempotencyStatsResponse(
            total_cached_operations=stats.get("total_cached_operations", 0),
            cache_hit_rate=cache_hit_rate,
            sample_keys=stats.get("sample_keys", [])
        )
        
    except Exception as e:
        logger.error("Failed to get idempotency stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas de idempotencia: {str(e)}"
        )


@router.post(
    "/circuit-breakers/{breaker_name}/reset",
    summary="Resetear circuit breaker",
    description="Resetea un circuit breaker específico al estado CLOSED"
)
async def reset_circuit_breaker(breaker_name: str):
    """Reset a specific circuit breaker"""
    
    try:
        success = await CircuitBreakerRegistry.reset_breaker(breaker_name)
        
        if success:
            logger.info(f"Circuit breaker '{breaker_name}' reset successfully")
            return {"message": f"Circuit breaker '{breaker_name}' reset to CLOSED state"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{breaker_name}' not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker '{breaker_name}'", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al resetear circuit breaker: {str(e)}"
        )


@router.delete(
    "/idempotency/cache/{operation_key}",
    summary="Invalidar cache de idempotencia",
    description="Elimina una entrada específica del cache de idempotencia"
)
async def invalidate_idempotency_cache(operation_key: str):
    """Invalidate specific idempotency cache entry"""
    
    try:
        idempotency_manager = get_idempotency_manager(redis_client)
        success = idempotency_manager.invalidate(operation_key)
        
        if success:
            logger.info(f"Idempotency cache invalidated for key: {operation_key}")
            return {"message": f"Cache invalidated for operation: {operation_key}"}
        else:
            return {"message": f"No cache entry found for operation: {operation_key}"}
            
    except Exception as e:
        logger.error(f"Failed to invalidate idempotency cache for '{operation_key}'", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al invalidar cache: {str(e)}"
        )


@router.post(
    "/health-check/enhanced",
    response_model=TaskResponse,
    summary="Enhanced health check",
    description="Health check con verificación de circuit breakers y saga system"
)
async def enhanced_health_check():
    """Enhanced health check including all system components"""
    
    correlation_id = str(uuid.uuid4())
    
    try:
        task = health_check_task.delay()
        
        # Store enhanced metadata
        task_metadata = {
            "correlation_id": correlation_id,
            "created_at": datetime.now().isoformat(),
            "task_type": "enhanced_health_check"
        }
        redis_client.setex(
            f"task_metadata:{task.id}",
            300,  # 5 minutes TTL
            json.dumps(task_metadata)
        )
        
        return TaskResponse(
            task_id=task.id,
            status="QUEUED",
            message="Enhanced health check encolado",
            correlation_id=correlation_id
        )
        
    except Exception as e:
        logger.error("Failed to start enhanced health check", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en enhanced health check: {str(e)}"
        )


# Backward compatibility - keep existing endpoints
@router.post(
    "/inscripciones/async",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear inscripción asíncrona (Legacy)",
    description="Endpoint legacy para compatibilidad"
)
async def create_inscription_async_legacy(
    inscription_data: InscripcionCreate, db: Session = Depends(get_db)
):
    """Legacy endpoint for backward compatibility"""
    try:
        data = {
            "registro_academico": inscription_data.registro_academico,
            "codigo_periodo": inscription_data.codigo_periodo,
            "grupos": inscription_data.grupos,
        }
        
        task = create_inscription_task.delay(data)
        
        return TaskResponse(
            task_id=task.id,
            status="QUEUED",
            message="Inscripción encolada para procesamiento asíncrono",
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al encolar tarea: {str(e)}",
        )


# Add all other existing endpoints from the original queue.py for compatibility
# (get_task_status, cancel_task, get_queue_stats, get_workers, control_workers, etc.)
# ... [Include all other endpoints from original file for backward compatibility]
