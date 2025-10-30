from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import redis
import json
import uuid
import logging
from datetime import datetime
from celery import current_app
from celery.result import AsyncResult

from app.core.database_sync import get_db
from app.core.config import settings
from app.core.celery_app import celery_app
# Enhanced imports for new functionality
from app.circuit_breaker import CircuitBreakerRegistry, circuit_breaker_registry, database_circuit_breaker
from app.idempotency import IdempotencyManager, idempotency_manager, inscription_idempotency
from app.saga_pattern import SagaTransaction, InscriptionSagaOrchestrator, saga_manager
# DISABLED: from app.enhanced_logging import StructuredLogger, CorrelationManager, structured_logger
from app.schemas import InscripcionCreate
from app.tasks import (
    create_inscription_task,
    create_enhanced_inscription_task,
    bulk_create_inscriptions_task,
    health_check_task,
    create_single_group_inscription_task,
)

router = APIRouter(prefix="/queue", tags=["Queue Management"])

# Use standard logging instead of enhanced logging to avoid coroutine issues
logger = logging.getLogger(__name__)

# Simple correlation ID manager (replacement for disabled enhanced_logging)
class SimpleCorrelationManager:
    @staticmethod
    def get_or_create_correlation_id():
        return f"corr_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def get_correlation_id():
        return f"corr_{uuid.uuid4().hex[:8]}"

CorrelationManager = SimpleCorrelationManager()

# Use the global singletons from the modules
# circuit_breaker_registry = CircuitBreakerRegistry()
# idempotency_manager = IdempotencyManager()
# saga_manager = InscriptionSagaOrchestrator()

# Conexión a Redis para información adicional
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


# Esquemas para el sistema de colas
class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    progress: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class MultipleTasksResponse(BaseModel):
    main_task_id: str
    group_tasks: List[Dict[str, str]]  # [{"grupo": "G1MAT207", "task_id": "xxx"}]
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    current: Optional[int] = None
    total: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class QueueStatsResponse(BaseModel):
    active_tasks: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    workers_online: int


class WorkerControlRequest(BaseModel):
    action: str  # "start", "stop", "restart"
    worker_name: Optional[str] = None


@router.post(
    "/inscripciones/async",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear inscripción asíncrona",
    description="Encola una tarea para crear una inscripción y retorna el task_id para monitoreo",
)
async def create_inscription_async(
    inscription_data: InscripcionCreate, db: Session = Depends(get_db)
):
    """Crear inscripción de forma asíncrona usando Celery"""
    try:
        # Convertir a dict para Celery
        data = {
            "registro_academico": inscription_data.registro_academico,
            "codigo_periodo": inscription_data.codigo_periodo,
            "grupos": inscription_data.grupos,
        }

        # Encolar la tarea
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


@router.post(
    "/inscripciones/async-by-groups",
    response_model=MultipleTasksResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear inscripción con task_id por grupo (ENHANCED)",
    description="Encola una tarea por cada grupo usando saga pattern, circuit breakers e idempotencia",
)
def create_inscription_async_by_groups(
    inscription_data: InscripcionCreate
):
    """Crear inscripción con una tarea por grupo usando funcionalidades mejoradas"""
    try:
        # Generate simple correlation ID for request tracking
        correlation_id = f"corr_{uuid.uuid4().hex[:8]}"
        
        # Generar código de inscripción principal
        main_codigo_inscripcion = (
            f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
        )

        # Datos base para todas las tareas
        base_data = {
            "registro_academico": inscription_data.registro_academico,
            "codigo_periodo": inscription_data.codigo_periodo,
            "correlation_id": correlation_id,
            "idempotency_key": f"inscription:{uuid.uuid4().hex}"
        }

        # Crear una tarea separada por cada grupo (tareas reales de Celery)
        group_tasks = []
        main_task_id = None
        
        for i, grupo in enumerate(inscription_data.grupos):
            # Datos específicos para este grupo
            group_data = {
                **base_data,
                "grupos": [grupo]  # Un grupo por tarea
            }
            
            # Crear tarea real de Celery para este grupo
            task = create_enhanced_inscription_task.delay(group_data)
            
            if i == 0:
                # Primera tarea es la "principal"
                main_task_id = task.id
            
            group_tasks.append({
                "grupo": grupo,
                "task_id": task.id  # ID real de Celery
            })

        response = MultipleTasksResponse(
            main_task_id=main_task_id,
            group_tasks=group_tasks,
            status="QUEUED",
            message=f"Inscripción encolada: {len(group_tasks)} tareas creadas (una por grupo)",
        )
        
        # Return queued response
        logger.info(
            "Enhanced inscription request queued with real task IDs",
            extra={
                "correlation_id": correlation_id,
                "main_task_id": main_task_id,
                "grupos_count": len(group_tasks),
                "group_tasks": [(t["grupo"], t["task_id"]) for t in group_tasks]
            }
        )

        return response

    except Exception as e:
        logger.error(
            "Enhanced inscription request failed",
            extra={
                "correlation_id": correlation_id if 'correlation_id' in locals() else None,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al encolar tareas mejoradas: {str(e)}",
        )


@router.post(
    "/inscripciones/bulk-async",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear múltiples inscripciones asíncronas",
    description="Encola una tarea para crear múltiples inscripciones en lote",
)
async def create_bulk_inscriptions_async(
    inscriptions_data: List[InscripcionCreate], db: Session = Depends(get_db)
):
    """Crear múltiples inscripciones de forma asíncrona"""
    try:
        # Convertir a lista de dicts
        data = []
        for inscription in inscriptions_data:
            data.append(
                {
                    "registro_academico": inscription.registro_academico,
                    "codigo_periodo": inscription.codigo_periodo,
                    "grupos": inscription.grupos,
                }
            )

        # Encolar la tarea de procesamiento en lote
        task = bulk_create_inscriptions_task.delay(data)

        return TaskResponse(
            task_id=task.id,
            status="QUEUED",
            message=f"Procesamiento en lote de {len(data)} inscripciones encolado",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al encolar tarea en lote: {str(e)}",
        )


@router.get(
    "/tasks/{task_id}/status",
    response_model=TaskStatusResponse,
    summary="Consultar estado de tarea",
    description="Obtiene el estado actual de una tarea específica",
)
async def get_task_status(task_id: str):
    """Obtener el estado de una tarea específica"""
    try:
        task_result = AsyncResult(task_id, app=celery_app)

        response = TaskStatusResponse(
            task_id=task_id, status=task_result.status, meta=None
        )

        # Manejo seguro del estado de la tarea
        try:
            if task_result.successful():
                response.result = task_result.result
            elif task_result.failed():
                # Manejo defensivo de la información de error
                error_info = task_result.info
                if isinstance(error_info, dict):
                    response.meta = error_info
                elif error_info is not None:
                    response.meta = {
                        "error_type": type(error_info).__name__,
                        "error_message": str(error_info),
                    }
                else:
                    response.meta = {
                        "error_type": "UnknownError",
                        "error_message": "Task failed with no error information",
                    }
            elif isinstance(task_result.info, dict):
                response.meta = task_result.info
            else:
                # Para estados PENDING, STARTED, etc.
                response.meta = {"message": f"Task is in {task_result.status} state"}
        except Exception as info_error:
            # Si hay error accediendo a la info de la tarea
            response.meta = {
                "error_type": "TaskInfoError",
                "error_message": f"Error accessing task info: {str(info_error)}",
            }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar estado de tarea: {type(e).__name__}: {str(e)}",
        )


@router.post(
    "/tasks/status/multiple",
    response_model=List[TaskStatusResponse],
    summary="Consultar estado de múltiples tareas",
    description="Obtiene el estado de múltiples tareas de una vez",
)
async def get_multiple_tasks_status(task_ids: List[str]):
    """Obtener el estado de múltiples tareas"""
    try:
        results = []
        for task_id in task_ids:
            try:
                task_result = AsyncResult(task_id, app=celery_app)

                response = TaskStatusResponse(
                    task_id=task_id, status=task_result.status, meta=None
                )

                # Manejo seguro de la información de la tarea
                try:
                    if task_result.failed():
                        exc = task_result.info
                        response.meta = {
                            "error_type": type(exc).__name__ if exc else None,
                            "error_message": str(exc),
                        }
                    elif isinstance(task_result.info, dict):
                        response.meta = task_result.info
                    else:
                        response.meta = {
                            "message": f"Task is in {task_result.status} state"
                        }
                except Exception:
                    response.meta = {
                        "error_type": "TaskInfoError",
                        "error_message": "Error accessing task info",
                    }

                # Si la tarea fue exitosa, incluir resultado
                if task_result.successful():
                    response.result = task_result.result

                results.append(response)

            except Exception as task_error:
                # Si hay error con una tarea específica, incluir el error
                results.append(
                    TaskStatusResponse(
                        task_id=task_id,
                        status="ERROR",
                        meta={
                            "error_type": type(task_error).__name__,
                            "error_message": f"Error accessing task: {str(task_error)}",
                        },
                    )
                )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar estados: {type(e).__name__}: {str(e)}",
        )


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar tarea",
    description="Cancela una tarea pendiente o en progreso",
)
async def cancel_task(task_id: str):
    """Cancelar una tarea específica"""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {"message": f"Tarea {task_id} cancelada"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cancelar tarea: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=QueueStatsResponse,
    summary="Estadísticas de colas (ENHANCED)",
    description="Obtiene estadísticas generales del sistema de colas con información mejorada",
)
async def get_queue_stats():
    """Obtener estadísticas del sistema de colas con mejoras"""
    try:
        correlation_id = CorrelationManager.get_or_create_correlation_id()
        
        logger.debug(
            "Getting enhanced queue statistics",
            extra={"correlation_id": correlation_id}
        )
        
        # Obtener estadísticas de Celery con circuit breaker protection
        stats_circuit_breaker = circuit_breaker_registry.get_circuit_breaker("celery_stats")
        
        async def _get_celery_stats():
            inspect = celery_app.control.inspect()

            # Tareas activas
            active_tasks = inspect.active()
            active_count = sum(len(tasks) for tasks in (active_tasks or {}).values())

            # Tareas pendientes (scheduled + reserved)
            scheduled_tasks = inspect.scheduled()
            reserved_tasks = inspect.reserved()

            scheduled_count = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
            reserved_count = sum(len(tasks) for tasks in (reserved_tasks or {}).values())
            pending_count = scheduled_count + reserved_count

            # Workers online
            stats = inspect.stats()
            workers_online = len(stats or {})

            return {
                "active_count": active_count,
                "pending_count": pending_count,
                "workers_online": workers_online
            }
        
        # Get Celery stats with circuit breaker protection
        try:
            celery_stats = await stats_circuit_breaker.call(_get_celery_stats)
        except Exception as e:
            logger.warning(
                "Celery stats failed, using fallback values",
                extra={"correlation_id": correlation_id, "error": str(e)}
            )
            celery_stats = {
                "active_count": 0,
                "pending_count": 0,
                "workers_online": 0
            }

        # Estadísticas adicionales desde Redis con fallback
        try:
            completed_tasks = int(redis_client.get("completed_tasks") or 0)
            failed_tasks = int(redis_client.get("failed_tasks") or 0)
        except Exception as e:
            logger.warning(
                "Redis stats failed, using fallback values",
                extra={"correlation_id": correlation_id, "error": str(e)}
            )
            completed_tasks = 0
            failed_tasks = 0

        response = QueueStatsResponse(
            active_tasks=celery_stats["active_count"],
            pending_tasks=celery_stats["pending_count"],
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            workers_online=celery_stats["workers_online"],
        )
        
        logger.debug(
            "Enhanced queue statistics retrieved successfully",
            extra={
                "correlation_id": correlation_id,
                "active_tasks": response.active_tasks,
                "workers_online": response.workers_online
            }
        )
        
        return response

    except Exception as e:
        logger.error(
            "Enhanced queue statistics failed",
            extra={
                "correlation_id": CorrelationManager.get_correlation_id(),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas mejoradas: {str(e)}",
        )


@router.get(
    "/workers",
    summary="Listar workers",
    description="Obtiene información de todos los workers activos",
)
async def get_workers():
    """Obtener información de workers"""
    try:
        inspect = celery_app.control.inspect()

        # Información de workers
        stats = inspect.stats() or {}
        active = inspect.active() or {}

        workers_info = []
        for worker_name, worker_stats in stats.items():
            workers_info.append(
                {
                    "name": worker_name,
                    "status": "online",
                    "active_tasks": len(active.get(worker_name, [])),
                    "processed_tasks": worker_stats.get("total", {}).get(
                        "tasks.inscription_worker.create_inscription_task", 0
                    ),
                    "load_avg": worker_stats.get("rusage", {}).get("utime", 0),
                    "pool": worker_stats.get("pool", {}),
                }
            )

        return {"workers": workers_info}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información de workers: {str(e)}",
        )


@router.post(
    "/workers/control",
    summary="Controlar workers",
    description="Permite iniciar, detener o reiniciar workers",
)
async def control_workers(control_request: WorkerControlRequest):
    """Controlar workers (iniciar, detener, reiniciar)"""
    try:
        action = control_request.action.lower()
        worker_name = control_request.worker_name

        if action == "stop":
            if worker_name:
                celery_app.control.shutdown([worker_name])
                message = f"Worker {worker_name} detenido"
            else:
                celery_app.control.shutdown()
                message = "Todos los workers detenidos"

        elif action == "restart":
            # Restart individual workers is complex, usually done at system level
            message = "Reinicio de workers debe hacerse a nivel de sistema"

        elif action == "ping":
            pong = celery_app.control.ping()
            return {"action": "ping", "response": pong}

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Acción no válida: {action}",
            )

        return {"action": action, "message": message}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al controlar workers: {str(e)}",
        )


@router.post(
    "/health-check",
    summary="Health check de workers (ENHANCED)",
    description="Ejecuta una tarea de health check con circuit breaker protection",
)
async def health_check_workers():
    """Ejecutar health check en workers con protección de circuit breaker"""
    try:
        correlation_id = CorrelationManager.get_or_create_correlation_id()
        
        # Use circuit breaker for health check
        health_circuit_breaker = circuit_breaker_registry.get_circuit_breaker("health_check")
        
        logger.info(
            "Starting enhanced health check",
            extra={"correlation_id": correlation_id}
        )
        
        # Execute health check with circuit breaker protection
        async def _health_check():
            task = health_check_task.delay()
            return TaskResponse(
                task_id=task.id, 
                status="QUEUED", 
                message="Enhanced health check encolado con circuit breaker protection"
            )
        
        result = await health_circuit_breaker.call(_health_check)
        
        logger.info(
            "Enhanced health check completed successfully",
            extra={"correlation_id": correlation_id, "task_id": result.task_id}
        )
        
        return result

    except Exception as e:
        logger.error(
            "Enhanced health check failed",
            extra={
                "correlation_id": CorrelationManager.get_correlation_id(),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en enhanced health check: {str(e)}",
        )


@router.get(
    "/queues",
    summary="Estado de colas",
    description="Obtiene información detallada de todas las colas",
)
async def get_queues_info():
    """Obtener información de las colas"""
    try:
        inspect = celery_app.control.inspect()

        # Información de colas activas
        active_queues = inspect.active_queues() or {}

        queues_info = {}
        for worker_name, queues in active_queues.items():
            for queue in queues:
                queue_name = queue.get("name", "unknown")
                if queue_name not in queues_info:
                    queues_info[queue_name] = {
                        "name": queue_name,
                        "workers": [],
                        "routing_key": queue.get("routing_key"),
                        "exchange": queue.get("exchange", {}).get("name"),
                    }
                queues_info[queue_name]["workers"].append(worker_name)

        return {"queues": list(queues_info.values())}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información de colas: {str(e)}",
        )


# ===== ENHANCED ENDPOINTS =====

@router.get(
    "/stats/enhanced",
    summary="Estadísticas mejoradas del sistema",
    description="Obtiene estadísticas completas incluyendo circuit breakers, sagas e idempotencia"
)
async def get_enhanced_stats():
    """Obtener estadísticas mejoradas del sistema"""
    try:
        # Get basic stats
        basic_stats = await get_queue_stats()
        
        # Get circuit breaker stats
        circuit_breaker_stats = circuit_breaker_registry.get_all_stats()
        
        # Get saga stats
        saga_stats = await saga_manager.get_statistics()
        
        # Get idempotency stats
        idempotency_stats = idempotency_manager.get_cache_statistics()
        
        return {
            **basic_stats.dict(),
            "circuit_breakers": circuit_breaker_stats,
            "saga_transactions": saga_stats,
            "idempotency_cache": idempotency_stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas mejoradas: {str(e)}",
        )


@router.get(
    "/circuit-breakers",
    summary="Estado de circuit breakers",
    description="Obtiene el estado actual de todos los circuit breakers"
)
async def get_circuit_breakers_status():
    """Obtener estado de circuit breakers"""
    try:
        circuit_breakers = circuit_breaker_registry.get_all_stats()
        
        # Determine overall health
        overall_health = "healthy"
        degraded_services = []
        
        for name, stats in circuit_breakers.items():
            if stats.get("state") == "open":
                overall_health = "degraded"
                degraded_services.append(name)
            elif stats.get("state") == "half_open":
                if overall_health == "healthy":
                    overall_health = "recovering"
        
        return {
            "circuit_breakers": circuit_breakers,
            "overall_health": overall_health,
            "degraded_services": degraded_services
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado de circuit breakers: {str(e)}",
        )


@router.get(
    "/sagas",
    summary="Transacciones saga activas",
    description="Obtiene información de todas las transacciones saga"
)
async def get_active_sagas():
    """Obtener transacciones saga activas"""
    try:
        correlation_id = CorrelationManager.get_or_create_correlation_id()
        
        logger.debug(
            "Getting active sagas",
            extra={"correlation_id": correlation_id}
        )
        
        active_sagas = await saga_manager.get_active_sagas()
        
        logger.debug(
            "Active sagas retrieved successfully",
            extra={
                "correlation_id": correlation_id,
                "sagas_count": len(active_sagas)
            }
        )
        
        return active_sagas
        
    except Exception as e:
        logger.error(
            "Failed to get active sagas",
            extra={
                "correlation_id": CorrelationManager.get_correlation_id(),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener sagas activas: {str(e)}",
        )


@router.get(
    "/idempotency/cache",
    summary="Estadísticas de cache de idempotencia",
    description="Obtiene información del cache de idempotencia"
)
async def get_idempotency_cache_stats():
    """Obtener estadísticas del cache de idempotencia"""
    try:
        stats = idempotency_manager.get_cache_statistics()
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas de cache: {str(e)}",
        )


@router.post(
    "/circuit-breakers/{service_name}/reset",
    summary="Reset circuit breaker",
    description="Resetea manualmente un circuit breaker específico"
)
async def reset_circuit_breaker(service_name: str):
    """Reset manual de circuit breaker"""
    try:
        circuit_breaker_registry.reset_circuit_breaker(service_name)
        return {"message": f"Circuit breaker '{service_name}' reseteado exitosamente"}
        
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{service_name}' no encontrado"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al resetear circuit breaker: {str(e)}",
        )


@router.delete(
    "/idempotency/cache/{key}",
    summary="Invalidar cache de idempotencia",
    description="Invalida manualmente una entrada del cache de idempotencia"
)
async def invalidate_idempotency_cache(key: str):
    """Invalidar cache de idempotencia manualmente"""
    try:
        correlation_id = CorrelationManager.get_or_create_correlation_id()
        
        logger.info(
            "Invalidating idempotency cache entry",
            extra={"correlation_id": correlation_id, "cache_key": key}
        )
        
        success = idempotency_manager.invalidate_cache_entry(key)
        
        if success:
            logger.info(
                "Idempotency cache entry invalidated successfully",
                extra={"correlation_id": correlation_id, "cache_key": key}
            )
            return {"message": f"Cache invalidado para clave: {key}"}
        else:
            logger.warning(
                "Idempotency cache key not found",
                extra={"correlation_id": correlation_id, "cache_key": key}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clave no encontrada en cache: {key}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to invalidate idempotency cache",
            extra={
                "correlation_id": CorrelationManager.get_correlation_id(),
                "cache_key": key,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al invalidar cache: {str(e)}",
        )


@router.post(
    "/sagas/cleanup",
    summary="Limpieza de sagas completadas",
    description="Limpia sagas antiguas completadas/fallidas para liberar memoria"
)
async def cleanup_completed_sagas(max_age_hours: int = 24):
    """Limpiar sagas completadas antiguas"""
    try:
        correlation_id = CorrelationManager.get_or_create_correlation_id()
        
        logger.info(
            "Starting saga cleanup",
            extra={"correlation_id": correlation_id, "max_age_hours": max_age_hours}
        )
        
        cleaned_count = await saga_manager.cleanup_completed_sagas(max_age_hours)
        
        logger.info(
            "Saga cleanup completed",
            extra={
                "correlation_id": correlation_id,
                "cleaned_sagas": cleaned_count,
                "max_age_hours": max_age_hours
            }
        )
        
        return {
            "message": f"Limpieza completada: {cleaned_count} sagas eliminadas",
            "cleaned_count": cleaned_count,
            "max_age_hours": max_age_hours
        }
        
    except Exception as e:
        logger.error(
            "Saga cleanup failed",
            extra={
                "correlation_id": CorrelationManager.get_correlation_id(),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en limpieza de sagas: {str(e)}",
        )
