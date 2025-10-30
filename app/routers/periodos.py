from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.services import PeriodoAcademicoService
from app.schemas import (
    PeriodoAcademicoCreate, PeriodoAcademicoResponse,
    PeriodoAcademicoUpdate
)

router = APIRouter(prefix="/periodos", tags=["Períodos Académicos"])

@router.post("/",
            response_model=PeriodoAcademicoResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Crear período académico",
            description="Crea un nuevo período académico")
async def create_periodo(
    periodo_data: PeriodoAcademicoCreate,
    db: AsyncSession = Depends(get_db)
):
    service = PeriodoAcademicoService(db)
    try:
        periodo = await service.create_periodo(periodo_data)
        return periodo
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/activo",
           response_model=PeriodoAcademicoResponse,
           summary="Obtener período activo",
           description="Obtiene el período académico actualmente activo")
async def get_periodo_activo(
    db: AsyncSession = Depends(get_db)
):
    service = PeriodoAcademicoService(db)
    periodo = await service.get_periodo_activo()
    
    if not periodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay un período académico activo"
        )
    
    return periodo

@router.get("/",
           response_model=List[PeriodoAcademicoResponse],
           summary="Obtener todos los períodos",
           description="Obtiene todos los períodos académicos registrados")
async def get_all_periodos(
    db: AsyncSession = Depends(get_db)
):
    service = PeriodoAcademicoService(db)
    return await service.get_all_periodos()
