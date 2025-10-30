from fastapi import APIRouter, Depends, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.logging import get_logger
from app.services.historial_service import HistorialAcademicoService
from app.schemas import (
    HistorialAcademicoCreate, HistorialAcademicoUpdate, HistorialAcademicoResponse,
    HistorialAcademicoCompleto, ResumenAcademico, HistorialPorPeriodo
)
from app.exceptions import HistorialNoEncontradoException

# Logger específico para este router
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/historial", tags=["Historial Académico"])

@router.post("/",
            response_model=HistorialAcademicoResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Crear registro de historial académico",
            description="Crea un nuevo registro en el historial académico de un estudiante")
async def create_historial(
    historial_data: HistorialAcademicoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Crea un nuevo registro en el historial académico.
    
    - **registro_academico**: Código del estudiante
    - **sigla_materia**: Sigla de la materia
    - **codigo_periodo**: Código del período académico
    - **nota_final**: Nota final (0-100, opcional)
    - **estado**: Estado de la materia (APROBADA, REPROBADA, RETIRADA)
    - **observacion**: Observaciones adicionales (opcional)
    """
    logger.info(
        f"Creando registro de historial académico",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": historial_data.registro_academico,
            "sigla_materia": historial_data.sigla_materia,
            "codigo_periodo": historial_data.codigo_periodo,
            "estado": historial_data.estado
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.create_historial(historial_data)
    
    logger.info(
        f"Registro de historial creado exitosamente",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": result.id_historial,
            "registro_academico": result.registro_academico
        }
    )
    
    return result

@router.get("/{id_historial}",
           response_model=HistorialAcademicoCompleto,
           summary="Obtener registro por ID",
           description="Obtiene un registro específico del historial académico")
async def get_historial_by_id(
    id_historial: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene un registro del historial académico por su ID"""
    logger.debug(
        f"Consultando historial por ID",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial
        }
    )
    
    service = HistorialAcademicoService(db)
    historial = await service.get_historial_by_id(id_historial)
    
    if not historial:
        logger.warning(
            f"Historial no encontrado",
            extra={
                "request_id": getattr(request.state, 'request_id', None),
                "id_historial": id_historial
            }
        )
        raise HistorialNoEncontradoException(str(id_historial))
    
    logger.debug(
        f"Historial encontrado exitosamente",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial,
            "registro_academico": historial.registro_academico
        }
    )
    
    return historial

@router.get("/estudiante/{registro_academico}",
           response_model=List[HistorialAcademicoResponse],
           summary="Obtener historial de estudiante",
           description="Obtiene todo el historial académico de un estudiante")
async def get_historial_estudiante(
    registro_academico: str,
    request: Request,
    codigo_periodo: Optional[str] = Query(None, description="Filtrar por período específico"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (APROBADA, REPROBADA, RETIRADA)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el historial académico completo de un estudiante.
    
    Parámetros opcionales de filtrado:
    - **codigo_periodo**: Filtrar por un período específico
    - **estado**: Filtrar por estado de materias
    """
    logger.info(
        f"Consultando historial de estudiante",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "filtros": {
                "codigo_periodo": codigo_periodo,
                "estado": estado
            }
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.get_historial_estudiante(registro_academico, codigo_periodo, estado)
    
    logger.info(
        f"Historial de estudiante consultado",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "total_registros": len(result)
        }
    )
    
    return result

@router.get("/estudiante/{registro_academico}/por-periodo",
           response_model=List[HistorialPorPeriodo],
           summary="Obtener historial agrupado por período",
           description="Obtiene el historial académico agrupado por períodos")
async def get_historial_por_periodo(
    registro_academico: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene el historial académico agrupado por períodos académicos"""
    logger.info(
        f"Consultando historial por período",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.get_historial_por_periodo(registro_academico)
    
    logger.info(
        f"Historial por período consultado",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "total_periodos": len(result)
        }
    )
    
    return result

@router.get("/estudiante/{registro_academico}/resumen",
           response_model=ResumenAcademico,
           summary="Obtener resumen académico",
           description="Obtiene un resumen estadístico del desempeño académico")
async def get_resumen_academico(
    registro_academico: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene un resumen estadístico del desempeño académico del estudiante.
    
    Incluye:
    - Total de materias cursadas
    - Materias por estado (aprobadas, reprobadas, retiradas)
    - Promedio general
    - Créditos aprobados
    """
    logger.info(
        f"Generando resumen académico",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.get_resumen_academico(registro_academico)
    
    logger.info(
        f"Resumen académico generado",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "total_materias": result.total_materias,
            "promedio_general": result.promedio_general
        }
    )
    
    return result

@router.get("/estudiante/{registro_academico}/estado/{estado}",
           response_model=List[HistorialAcademicoResponse],
           summary="Obtener materias por estado",
           description="Obtiene las materias de un estudiante filtradas por estado")
async def get_materias_por_estado(
    registro_academico: str,
    estado: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene las materias de un estudiante filtradas por estado específico.
    
    Estados válidos:
    - **APROBADA**: Materias aprobadas
    - **REPROBADA**: Materias reprobadas
    - **RETIRADA**: Materias retiradas
    """
    logger.info(
        f"Consultando materias por estado",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "estado": estado
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.get_materias_por_estado(registro_academico, estado)
    
    logger.info(
        f"Materias por estado consultadas",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "registro_academico": registro_academico,
            "estado": estado,
            "total_materias": len(result)
        }
    )
    
    return result

@router.put("/{id_historial}",
           response_model=HistorialAcademicoResponse,
           summary="Actualizar registro de historial",
           description="Actualiza un registro existente del historial académico")
async def update_historial(
    id_historial: int,
    historial_data: HistorialAcademicoUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza un registro del historial académico.
    
    Solo se pueden actualizar:
    - Nota final
    - Estado de la materia
    - Observaciones
    """
    logger.info(
        f"Actualizando registro de historial",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial,
            "campos_a_actualizar": list(historial_data.dict(exclude_unset=True).keys())
        }
    )
    
    service = HistorialAcademicoService(db)
    result = await service.update_historial(id_historial, historial_data)
    
    logger.info(
        f"Registro de historial actualizado exitosamente",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial,
            "registro_academico": result.registro_academico
        }
    )
    
    return result

@router.delete("/{id_historial}",
              status_code=status.HTTP_204_NO_CONTENT,
              summary="Eliminar registro de historial",
              description="Elimina un registro del historial académico")
async def delete_historial(
    id_historial: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina un registro del historial académico.
    
    **Nota**: Esta operación es irreversible.
    """
    logger.warning(
        f"Eliminando registro de historial",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial
        }
    )
    
    service = HistorialAcademicoService(db)
    deleted = await service.delete_historial(id_historial)
    
    if not deleted:
        logger.error(
            f"No se pudo eliminar el historial - no encontrado",
            extra={
                "request_id": getattr(request.state, 'request_id', None),
                "id_historial": id_historial
            }
        )
        raise HistorialNoEncontradoException(str(id_historial))
    
    logger.warning(
        f"Registro de historial eliminado exitosamente",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "id_historial": id_historial
        }
    )

# Endpoints adicionales de estadísticas y reportes

@router.get("/reportes/estudiantes-por-materia/{sigla_materia}",
           summary="Reporte de estudiantes por materia",
           description="Obtiene estadísticas de estudiantes que han cursado una materia")
async def get_reporte_materia(
    sigla_materia: str,
    request: Request,
    codigo_periodo: Optional[str] = Query(None, description="Filtrar por período"),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene un reporte de estudiantes que han cursado una materia específica.
    
    Incluye estadísticas de aprobación, reprobación y retiros.
    """
    logger.info(
        f"Generando reporte de materia",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "sigla_materia": sigla_materia,
            "codigo_periodo": codigo_periodo
        }
    )
    
    service = HistorialAcademicoService(db)
    # Esta funcionalidad se puede implementar como extensión
    logger.info(
        f"Reporte de materia - funcionalidad en desarrollo",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "sigla_materia": sigla_materia
        }
    )
    
    return {"message": "Funcionalidad en desarrollo", "materia": sigla_materia}

@router.get("/reportes/rendimiento-periodo/{codigo_periodo}",
           summary="Reporte de rendimiento por período",
           description="Obtiene estadísticas generales de rendimiento académico por período")
async def get_reporte_periodo(
    codigo_periodo: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene estadísticas generales de rendimiento académico para un período.
    
    Incluye promedios generales, tasas de aprobación, etc.
    """
    logger.info(
        f"Generando reporte de período",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "codigo_periodo": codigo_periodo
        }
    )
    
    service = HistorialAcademicoService(db)
    # Esta funcionalidad se puede implementar como extensión
    logger.info(
        f"Reporte de período - funcionalidad en desarrollo",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "codigo_periodo": codigo_periodo
        }
    )
    
    return {"message": "Funcionalidad en desarrollo", "periodo": codigo_periodo}