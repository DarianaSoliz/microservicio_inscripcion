from sqlalchemy.ext.asyncio import AsyncAsyncSession
from sqlalchemy import select, func, and_, desc, distinct
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal

from app.models import (
    HistorialAcademico, Estudiante, Materia, PeriodoAcademico
)
from app.schemas import (
    HistorialAcademicoCreate, HistorialAcademicoUpdate, HistorialAcademicoResponse,
    HistorialAcademicoCompleto, ResumenAcademico, HistorialPorPeriodo
)
from app.exceptions import (
    EstudianteNoEncontradoException, MateriaNoEncontradaException,
    PeriodoNoEncontradoException, HistorialNoEncontradoException,
    ValidationException, HistorialDuplicadoException, EstadoMateriaInvalidoException,
    NotaInvalidaException, DatabaseException
)
from app.core.logging import get_logger, log_service_operation, log_database_operation, log_execution_time

# Logger específico para este servicio
logger = get_logger(__name__)

ESTADOS_VALIDOS = ['APROBADA', 'REPROBADA', 'RETIRADA']


class HistorialAcademicoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger(f"{__name__}.HistorialAcademicoService")

    @log_service_operation("historial")
    @log_execution_time
    async def create_historial(self, historial_data: HistorialAcademicoCreate) -> HistorialAcademicoResponse:
        """Crear un nuevo registro en el historial académico"""
        
        self.logger.info(
            f"Creando registro de historial para estudiante {historial_data.registro_academico}",
            extra={
                "registro_academico": historial_data.registro_academico,
                "sigla_materia": historial_data.sigla_materia,
                "codigo_periodo": historial_data.codigo_periodo,
                "estado": historial_data.estado
            }
        )
        
        try:
            # Validar estado
            if historial_data.estado not in ESTADOS_VALIDOS:
                raise EstadoMateriaInvalidoException(historial_data.estado, ESTADOS_VALIDOS)
            
            # Validar nota si está presente
            if historial_data.nota_final is not None:
                if not (0 <= historial_data.nota_final <= 100):
                    raise NotaInvalidaException(historial_data.nota_final)
            
            # Validar que existe el estudiante
            result = await self.db.execute(
                select(Estudiante).where(Estudiante.registro_academico == historial_data.registro_academico)
            )
            if not result.scalar_one_or_none():
                self.logger.warning(f"Estudiante no encontrado: {historial_data.registro_academico}")
                raise EstudianteNoEncontradoException(historial_data.registro_academico)
            
            # Validar que existe la materia
            result = await self.db.execute(
                select(Materia).where(Materia.sigla == historial_data.sigla_materia)
            )
            if not result.scalar_one_or_none():
                self.logger.warning(f"Materia no encontrada: {historial_data.sigla_materia}")
                raise MateriaNoEncontradaException(historial_data.sigla_materia)
            
            # Validar que existe el período
            result = await self.db.execute(
                select(PeriodoAcademico).where(PeriodoAcademico.codigo_periodo == historial_data.codigo_periodo)
            )
            if not result.scalar_one_or_none():
                self.logger.warning(f"Período no encontrado: {historial_data.codigo_periodo}")
                raise PeriodoNoEncontradoException(historial_data.codigo_periodo)
            
            # Verificar que no existe un registro duplicado
            result = await self.db.execute(
                select(HistorialAcademico).where(
                    and_(
                        HistorialAcademico.registro_academico == historial_data.registro_academico,
                        HistorialAcademico.sigla_materia == historial_data.sigla_materia,
                        HistorialAcademico.codigo_periodo == historial_data.codigo_periodo
                    )
                )
            )
            if result.scalar_one_or_none():
                self.logger.warning(
                    f"Registro duplicado detectado",
                    extra={
                        "registro_academico": historial_data.registro_academico,
                        "sigla_materia": historial_data.sigla_materia,
                        "codigo_periodo": historial_data.codigo_periodo
                    }
                )
                raise HistorialDuplicadoException(
                    historial_data.registro_academico,
                    historial_data.sigla_materia,
                    historial_data.codigo_periodo
                )
            
            # Crear el registro
            historial = HistorialAcademico(**historial_data.dict())
            self.db.add(historial)
            await self.db.commit()
            await self.db.refresh(historial)
            
            self.logger.info(
                f"Registro de historial creado exitosamente: ID {historial.id_historial}",
                extra={
                    "id_historial": historial.id_historial,
                    "registro_academico": historial_data.registro_academico,
                    "sigla_materia": historial_data.sigla_materia
                }
            )
            
            return HistorialAcademicoResponse.from_orm(historial)
            
        except Exception as exc:
            self.logger.error(
                f"Error al crear registro de historial: {str(exc)}",
                extra={
                    "registro_academico": historial_data.registro_academico,
                    "sigla_materia": historial_data.sigla_materia,
                    "codigo_periodo": historial_data.codigo_periodo
                }
            )
            await self.db.rollback()
            if isinstance(exc, (EstadoMateriaInvalidoException, NotaInvalidaException, 
                              EstudianteNoEncontradoException, MateriaNoEncontradaException,
                              PeriodoNoEncontradoException, HistorialDuplicadoException)):
                raise exc
            raise DatabaseException("Error al crear registro de historial", exc, "CREATE")

    @log_service_operation("historial")
    @log_database_operation("READ")
    async def get_historial_by_id(self, id_historial: int) -> Optional[HistorialAcademicoCompleto]:
        """Obtener un registro del historial por ID"""
        
        self.logger.debug(f"Consultando historial por ID: {id_historial}")
        
        try:
            result = await self.db.execute(
                select(HistorialAcademico)
                .options(
                    selectinload(HistorialAcademico.estudiante),
                    selectinload(HistorialAcademico.materia),
                    selectinload(HistorialAcademico.periodo)
                )
                .where(HistorialAcademico.id_historial == id_historial)
            )
            historial = result.scalar_one_or_none()
            
            if not historial:
                self.logger.info(f"Historial no encontrado: ID {id_historial}")
                return None
            
            self.logger.debug(f"Historial encontrado: ID {id_historial}")
            return HistorialAcademicoCompleto.from_orm(historial)
            
        except Exception as exc:
            self.logger.error(f"Error al consultar historial por ID {id_historial}: {str(exc)}")
            raise DatabaseException("Error al consultar historial", exc, "READ")

    @log_service_operation("historial")
    @log_execution_time
    async def get_historial_estudiante(
        self, 
        registro_academico: str,
        codigo_periodo: Optional[str] = None,
        estado: Optional[str] = None
    ) -> List[HistorialAcademicoResponse]:
        """Obtener el historial académico de un estudiante"""
        
        self.logger.info(
            f"Consultando historial para estudiante {registro_academico}",
            extra={
                "registro_academico": registro_academico,
                "codigo_periodo": codigo_periodo,
                "estado": estado
            }
        )
        
        try:
            query = select(HistorialAcademico).where(
                HistorialAcademico.registro_academico == registro_academico
            )
            
            if codigo_periodo:
                query = query.where(HistorialAcademico.codigo_periodo == codigo_periodo)
            
            if estado:
                if estado not in ESTADOS_VALIDOS:
                    raise EstadoMateriaInvalidoException(estado, ESTADOS_VALIDOS)
                query = query.where(HistorialAcademico.estado == estado)
            
            query = query.order_by(desc(HistorialAcademico.fecha_registro))
            
            result = await self.db.execute(query)
            historiales = result.scalars().all()
            
            self.logger.info(
                f"Historial consultado: {len(historiales)} registros encontrados",
                extra={
                    "registro_academico": registro_academico,
                    "total_registros": len(historiales)
                }
            )
            
            return [HistorialAcademicoResponse.from_orm(h) for h in historiales]
            
        except Exception as exc:
            self.logger.error(
                f"Error al consultar historial de estudiante {registro_academico}: {str(exc)}"
            )
            if isinstance(exc, EstadoMateriaInvalidoException):
                raise exc
            raise DatabaseException("Error al consultar historial de estudiante", exc, "READ")

    @log_service_operation("historial")
    @log_execution_time
    async def get_historial_por_periodo(self, registro_academico: str) -> List[HistorialPorPeriodo]:
        """Obtener historial agrupado por período"""
        
        self.logger.info(f"Consultando historial por período para estudiante {registro_academico}")
        
        try:
            # Obtener períodos únicos del estudiante
            result = await self.db.execute(
                select(distinct(HistorialAcademico.codigo_periodo))
                .where(HistorialAcademico.registro_academico == registro_academico)
                .order_by(HistorialAcademico.codigo_periodo)
            )
            periodos = result.scalars().all()
            
            historial_por_periodo = []
            
            for codigo_periodo in periodos:
                # Obtener materias del período
                materias_resultado = await self.db.execute(
                    select(HistorialAcademico)
                    .where(
                        and_(
                            HistorialAcademico.registro_academico == registro_academico,
                            HistorialAcademico.codigo_periodo == codigo_periodo
                        )
                    )
                    .order_by(HistorialAcademico.sigla_materia)
                )
                materias = materias_resultado.scalars().all()
                
                # Calcular promedio del período
                notas_validas = [m.nota_final for m in materias if m.nota_final is not None and m.estado == 'APROBADA']
                promedio_periodo = sum(notas_validas) / len(notas_validas) if notas_validas else None
                
                # Obtener nombre del período
                periodo_resultado = await self.db.execute(
                    select(PeriodoAcademico).where(PeriodoAcademico.codigo_periodo == codigo_periodo)
                )
                periodo = periodo_resultado.scalar_one_or_none()
                periodo_nombre = f"{periodo.gestion} - {periodo.semestre}" if periodo else codigo_periodo
                
                historial_por_periodo.append(HistorialPorPeriodo(
                    codigo_periodo=codigo_periodo,
                    periodo_nombre=periodo_nombre,
                    materias=[HistorialAcademicoResponse.from_orm(m) for m in materias],
                    promedio_periodo=promedio_periodo
                ))
            
            self.logger.info(
                f"Historial por período consultado: {len(historial_por_periodo)} períodos encontrados",
                extra={
                    "registro_academico": registro_academico,
                    "total_periodos": len(historial_por_periodo)
                }
            )
            
            return historial_por_periodo
            
        except Exception as exc:
            self.logger.error(
                f"Error al consultar historial por período para estudiante {registro_academico}: {str(exc)}"
            )
            raise DatabaseException("Error al consultar historial por período", exc, "READ")

    @log_service_operation("historial")
    @log_execution_time
    async def get_resumen_academico(self, registro_academico: str) -> ResumenAcademico:
        """Obtener resumen académico del estudiante"""
        
        self.logger.info(f"Generando resumen académico para estudiante {registro_academico}")
        
        try:
            # Contar materias por estado
            result = await self.db.execute(
                select(
                    func.count(HistorialAcademico.id_historial).label('total'),
                    func.sum(func.case((HistorialAcademico.estado == 'APROBADA', 1), else_=0)).label('aprobadas'),
                    func.sum(func.case((HistorialAcademico.estado == 'REPROBADA', 1), else_=0)).label('reprobadas'),
                    func.sum(func.case((HistorialAcademico.estado == 'RETIRADA', 1), else_=0)).label('retiradas'),
                    func.avg(func.case((HistorialAcademico.estado == 'APROBADA', HistorialAcademico.nota_final))).label('promedio')
                )
                .where(HistorialAcademico.registro_academico == registro_academico)
            )
            stats = result.one()
            
            # Calcular créditos aprobados
            result = await self.db.execute(
                select(func.sum(Materia.creditos))
                .select_from(HistorialAcademico.join(Materia))
                .where(
                    and_(
                        HistorialAcademico.registro_academico == registro_academico,
                        HistorialAcademico.estado == 'APROBADA'
                    )
                )
            )
            creditos_aprobados = result.scalar() or 0
            
            resumen = ResumenAcademico(
                registro_academico=registro_academico,
                total_materias=stats.total or 0,
                materias_aprobadas=stats.aprobadas or 0,
                materias_reprobadas=stats.reprobadas or 0,
                materias_retiradas=stats.retiradas or 0,
                promedio_general=stats.promedio,
                creditos_aprobados=creditos_aprobados
            )
            
            self.logger.info(
                f"Resumen académico generado",
                extra={
                    "registro_academico": registro_academico,
                    "total_materias": resumen.total_materias,
                    "materias_aprobadas": resumen.materias_aprobadas,
                    "promedio_general": resumen.promedio_general,
                    "creditos_aprobados": resumen.creditos_aprobados
                }
            )
            
            return resumen
            
        except Exception as exc:
            self.logger.error(
                f"Error al generar resumen académico para estudiante {registro_academico}: {str(exc)}"
            )
            raise DatabaseException("Error al generar resumen académico", exc, "READ")

    @log_service_operation("historial")
    @log_database_operation("UPDATE")
    async def update_historial(
        self, 
        id_historial: int, 
        historial_data: HistorialAcademicoUpdate
    ) -> HistorialAcademicoResponse:
        """Actualizar un registro del historial"""
        
        self.logger.info(f"Actualizando registro de historial ID: {id_historial}")
        
        try:
            result = await self.db.execute(
                select(HistorialAcademico).where(HistorialAcademico.id_historial == id_historial)
            )
            historial = result.scalar_one_or_none()
            
            if not historial:
                self.logger.warning(f"Historial no encontrado para actualizar: ID {id_historial}")
                raise HistorialNoEncontradoException(str(id_historial))
            
            # Validar estado si se está actualizando
            if historial_data.estado and historial_data.estado not in ESTADOS_VALIDOS:
                raise EstadoMateriaInvalidoException(historial_data.estado, ESTADOS_VALIDOS)
            
            # Validar nota si se está actualizando
            if historial_data.nota_final is not None:
                if not (0 <= historial_data.nota_final <= 100):
                    raise NotaInvalidaException(historial_data.nota_final)
            
            # Actualizar campos
            update_data = historial_data.dict(exclude_unset=True)
            campos_actualizados = []
            for field, value in update_data.items():
                old_value = getattr(historial, field)
                setattr(historial, field, value)
                if old_value != value:
                    campos_actualizados.append(f"{field}: {old_value} -> {value}")
            
            await self.db.commit()
            await self.db.refresh(historial)
            
            self.logger.info(
                f"Registro de historial actualizado exitosamente",
                extra={
                    "id_historial": id_historial,
                    "campos_actualizados": campos_actualizados
                }
            )
            
            return HistorialAcademicoResponse.from_orm(historial)
            
        except Exception as exc:
            self.logger.error(f"Error al actualizar historial ID {id_historial}: {str(exc)}")
            await self.db.rollback()
            if isinstance(exc, (HistorialNoEncontradoException, EstadoMateriaInvalidoException, NotaInvalidaException)):
                raise exc
            raise DatabaseException("Error al actualizar registro de historial", exc, "UPDATE")

    @log_service_operation("historial")
    @log_database_operation("DELETE")
    async def delete_historial(self, id_historial: int) -> bool:
        """Eliminar un registro del historial"""
        
        self.logger.info(f"Eliminando registro de historial ID: {id_historial}")
        
        try:
            result = await self.db.execute(
                select(HistorialAcademico).where(HistorialAcademico.id_historial == id_historial)
            )
            historial = result.scalar_one_or_none()
            
            if not historial:
                self.logger.warning(f"Historial no encontrado para eliminar: ID {id_historial}")
                return False
            
            registro_academico = historial.registro_academico
            sigla_materia = historial.sigla_materia
            
            await self.db.delete(historial)
            await self.db.commit()
            
            self.logger.info(
                f"Registro de historial eliminado exitosamente",
                extra={
                    "id_historial": id_historial,
                    "registro_academico": registro_academico,
                    "sigla_materia": sigla_materia
                }
            )
            
            return True
            
        except Exception as exc:
            self.logger.error(f"Error al eliminar historial ID {id_historial}: {str(exc)}")
            await self.db.rollback()
            raise DatabaseException("Error al eliminar registro de historial", exc, "DELETE")

    @log_service_operation("historial")
    @log_database_operation("READ")
    async def get_materias_por_estado(
        self, 
        registro_academico: str, 
        estado: str
    ) -> List[HistorialAcademicoResponse]:
        """Obtener materias de un estudiante filtradas por estado"""
        
        self.logger.info(
            f"Consultando materias por estado para estudiante {registro_academico}",
            extra={
                "registro_academico": registro_academico,
                "estado": estado
            }
        )
        
        try:
            if estado not in ESTADOS_VALIDOS:
                raise EstadoMateriaInvalidoException(estado, ESTADOS_VALIDOS)
            
            result = await self.db.execute(
                select(HistorialAcademico)
                .where(
                    and_(
                        HistorialAcademico.registro_academico == registro_academico,
                        HistorialAcademico.estado == estado
                    )
                )
                .order_by(desc(HistorialAcademico.fecha_registro))
            )
            historiales = result.scalars().all()
            
            self.logger.info(
                f"Materias por estado consultadas: {len(historiales)} registros encontrados",
                extra={
                    "registro_academico": registro_academico,
                    "estado": estado,
                    "total_registros": len(historiales)
                }
            )
            
            return [HistorialAcademicoResponse.from_orm(h) for h in historiales]
            
        except Exception as exc:
            self.logger.error(
                f"Error al consultar materias por estado para estudiante {registro_academico}: {str(exc)}"
            )
            if isinstance(exc, EstadoMateriaInvalidoException):
                raise exc
            raise DatabaseException("Error al consultar materias por estado", exc, "READ")
