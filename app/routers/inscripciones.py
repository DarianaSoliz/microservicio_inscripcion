from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database_sync import get_db
from app.services import InscripcionService, PeriodoAcademicoService
from app.schemas import (
    InscripcionCreate, InscripcionUpdate, InscripcionResponse, InscripcionSimpleResponse,
    InscripcionCompleteResponse, DetalleInscripcionCreate,
    EstadisticasInscripcion, ErrorResponse
)
from app.exceptions import InscripcionNoEncontradaException, DetalleInscripcionNoEncontradoException
from app.tasks import create_inscription_task
from app.core.logging import get_logger

# Logger específico para este router
logger = get_logger(__name__)

router = APIRouter(prefix="/inscripciones", tags=["Inscripciones"])

@router.post("/", 
            status_code=status.HTTP_202_ACCEPTED,
            summary="Crear nueva inscripción (Asíncrono)",
            description="Crea una nueva inscripción de forma asíncrona usando el sistema de colas. Retorna el task_id para monitorear el progreso.")
async def create_inscripcion(
    inscripcion_data: InscripcionCreate
):
    """
    Crea una nueva inscripción de forma asíncrona.
    
    Returns:
        dict: Contiene el task_id para monitorear el progreso
    """
    # Convertir los datos a diccionario para la tarea
    task_data = {
        "registro_academico": inscripcion_data.registro_academico,
        "codigo_periodo": inscripcion_data.codigo_periodo,
        "grupos": inscripcion_data.grupos
    }
    
    logger.info(f"Enviando tarea de inscripción para {task_data['registro_academico']} periodo {task_data['codigo_periodo']}")
    task = create_inscription_task.delay(task_data)
    
    return {
        "message": "Inscripción enviada a procesamiento asíncrono",
        "task_id": task.id,
        "status": "PENDING",
        "registro_academico": inscripcion_data.registro_academico,
        "monitor_url": f"/api/v1/queue/tasks/{task.id}/status"
    }

@router.post("/sync", 
            response_model=InscripcionResponse, 
            status_code=status.HTTP_201_CREATED,
            summary="Crear nueva inscripción (Síncrono)",
            description="Crea una nueva inscripción de forma síncrona. Solo para casos especiales donde se requiere respuesta inmediata.")
async def create_inscripcion_sync(
    inscripcion_data: InscripcionCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva inscripción de forma síncrona.
    
    Este endpoint está disponible para casos especiales donde se requiere 
    una respuesta inmediata, pero se recomienda usar el endpoint asíncrono principal.
    """
    service = InscripcionService(db)
    # Los errores son manejados por los exception handlers globales
    inscripcion = await service.create_inscripcion(inscripcion_data)
    return inscripcion

@router.get("/{codigo_inscripcion}",
           response_model=InscripcionResponse,
           summary="Obtener inscripción por código",
           description="Obtiene los detalles de una inscripción específica")
async def get_inscripcion(
    codigo_inscripcion: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    inscripcion = await service.get_inscripcion_by_codigo(codigo_inscripcion)
    
    if not inscripcion:
        raise InscripcionNoEncontradaException(codigo_inscripcion)
    
    return inscripcion

@router.get("/estudiante/{registro_academico}",
           summary="Obtener inscripciones de un estudiante",
           description="Obtiene todas las inscripciones de un estudiante específico")
async def get_inscripciones_estudiante(
    registro_academico: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    inscripciones = await service.get_inscripciones_by_estudiante(registro_academico)
    return {"inscripciones": inscripciones}

@router.get("/periodo/{codigo_periodo}",
           summary="Obtener inscripciones de un período",
           description="Obtiene todas las inscripciones de un período académico específico")
async def get_inscripciones_periodo(
    codigo_periodo: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    inscripciones = await service.get_inscripciones_by_periodo(codigo_periodo)
    return {"inscripciones": inscripciones}

@router.put("/{codigo_inscripcion}",
           response_model=InscripcionResponse,
           summary="Actualizar inscripción",
           description="Actualiza los datos de una inscripción existente")
async def update_inscripcion(
    codigo_inscripcion: str,
    inscripcion_data: InscripcionUpdate,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    inscripcion = await service.update_inscripcion(codigo_inscripcion, inscripcion_data)
    
    if not inscripcion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscripción no encontrada"
        )
    
    return inscripcion

@router.delete("/{codigo_inscripcion}",
              status_code=status.HTTP_204_NO_CONTENT,
              summary="Eliminar inscripción",
              description="Elimina una inscripción y todos sus detalles")
async def delete_inscripcion(
    codigo_inscripcion: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    deleted = await service.delete_inscripcion(codigo_inscripcion)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscripción no encontrada"
        )

@router.post("/{codigo_inscripcion}/grupos/{codigo_grupo}",
            summary="Agregar grupo a inscripción",
            description="Agrega un grupo adicional a una inscripción existente")
async def add_grupo_to_inscripcion(
    codigo_inscripcion: str,
    codigo_grupo: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    # Los errores son manejados por los exception handlers globales
    logger.info(f"Agregar grupo {codigo_grupo} a inscripcion {codigo_inscripcion}")
    detalle = await service.add_grupo_to_inscripcion(codigo_inscripcion, codigo_grupo)
    return {"message": "Grupo agregado exitosamente", "detalle": detalle.codigo_detalle}

@router.delete("/{codigo_inscripcion}/grupos/{codigo_grupo}",
              status_code=status.HTTP_200_OK,
              summary="Remover grupo de inscripción",
              description="Remueve un grupo de una inscripción existente")
async def remove_grupo_from_inscripcion(
    codigo_inscripcion: str,
    codigo_grupo: str,
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    logger.info(f"Remover grupo {codigo_grupo} de inscripcion {codigo_inscripcion}")
    removed = await service.remove_grupo_from_inscripcion(codigo_inscripcion, codigo_grupo)

    if not removed:
        raise DetalleInscripcionNoEncontradoException(codigo_inscripcion, codigo_grupo)

    return {
        "status": "SUCCESS",
        "message": f"Grupo {codigo_grupo} retirado correctamente",
        "codigo_inscripcion": codigo_inscripcion,
        "codigo_grupo": codigo_grupo
    }

@router.get("/estadisticas/general",
           response_model=EstadisticasInscripcion,
           summary="Obtener estadísticas de inscripciones",
           description="Obtiene estadísticas generales del sistema de inscripciones")
async def get_estadisticas_inscripcion(
    db: Session = Depends(get_db)
):
    service = InscripcionService(db)
    return await service.get_estadisticas_inscripcion()
