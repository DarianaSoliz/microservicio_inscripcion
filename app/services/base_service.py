from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import uuid

from app.models import (
    Inscripcion, DetalleInscripcion, PeriodoAcademico, 
    Estudiante, Grupo, Materia, Docente, Aula, Horario
)
from app.schemas import (
    InscripcionCreate, InscripcionUpdate, InscripcionResponse,
    DetalleInscripcionCreate, PeriodoAcademicoCreate,
    EstadisticasInscripcion
)
from app.exceptions import (
    InscripcionNoEncontradaException, GrupoDuplicadoException
)
from app.exceptions import (
    EstudianteNoEncontradoException,
    EstudianteBloqueadoException,
    PeriodoNoEncontradoException,
    PeriodoInactivoException,
    GrupoNoEncontradoException,
    GrupoSinCupoException,
    ConflictoHorarioException,
    InscripcionDuplicadaException,
    GrupoDuplicadoException,
    InscripcionNoEncontradaException
)
from app.core.logging import get_logger

# Logger específico para este servicio
logger = get_logger(__name__)

class InscripcionService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_inscripcion(self, inscripcion_data: InscripcionCreate) -> Inscripcion:
        """Crear una nueva inscripción con sus detalles"""
        
        # Generar código único para la inscripción (max 10 caracteres)
        codigo_inscripcion = f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
        
        logger.info(f"Crear inscripción para {inscripcion_data.registro_academico} periodo {inscripcion_data.codigo_periodo}")
        # Verificar que el estudiante existe y no esté bloqueado
        estudiante = await self.get_estudiante_by_registro(inscripcion_data.registro_academico)
        if not estudiante:
            logger.warning(f"Estudiante no encontrado: {inscripcion_data.registro_academico}")
            raise EstudianteNoEncontradoException(inscripcion_data.registro_academico)
        
        if estudiante.estado_academico == "BLOQUEADO":
            raise EstudianteBloqueadoException(
                inscripcion_data.registro_academico,
                "Estado académico bloqueado"
            )
        
        # Verificar que el período académico existe y está activo
        periodo = await self.get_periodo_by_codigo(inscripcion_data.codigo_periodo)
        if not periodo:
            raise PeriodoNoEncontradoException(inscripcion_data.codigo_periodo)
        
        if periodo.estado != "ACTIVO":
            logger.warning(f"Periodo inactivo: {inscripcion_data.codigo_periodo} estado {periodo.estado}")
            raise PeriodoInactivoException(inscripcion_data.codigo_periodo, periodo.estado)
        
        # Verificar que no existe una inscripción previa para este período
        existing_inscripcion = await self.db.execute(
            select(Inscripcion).where(
                and_(
                    Inscripcion.registro_academico == inscripcion_data.registro_academico,
                    Inscripcion.codigo_periodo == inscripcion_data.codigo_periodo
                )
            )
        )
        existing = existing_inscripcion.scalar_one_or_none()
        if existing:
            raise InscripcionDuplicadaException(
                inscripcion_data.registro_academico,
                inscripcion_data.codigo_periodo,
                existing.codigo_inscripcion
            )

        # Validar grupos y disponibilidad
        await self._validate_grupos_disponibilidad(inscripcion_data.grupos)
        await self._validate_horarios_conflicto(inscripcion_data.grupos)

        # Crear la inscripción
        nueva_inscripcion = Inscripcion(
            codigo_inscripcion=codigo_inscripcion,
            registro_academico=inscripcion_data.registro_academico,
            codigo_periodo=inscripcion_data.codigo_periodo,
            fecha_inscripcion=date.today()
        )

        self.db.add(nueva_inscripcion)
        await self.db.flush()

        # Crear los detalles de inscripción
        detalles_creados = []
        for codigo_grupo in inscripcion_data.grupos:
            codigo_detalle = f"D{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"

            detalle = DetalleInscripcion(
                codigo_detalle=codigo_detalle,
                codigo_inscripcion=codigo_inscripcion,
                codigo_grupo=codigo_grupo
            )

            self.db.add(detalle)
            detalles_creados.append(detalle)

            # Actualizar contador de inscritos en el grupo
            await self._increment_grupo_inscritos(codigo_grupo)
            logger.info(f"Incrementado inscritos para grupo {codigo_grupo}")

        await self.db.commit()

        # Recargar la inscripción con relaciones
        result = await self.db.execute(
            select(Inscripcion)
            .options(
                selectinload(Inscripcion.estudiante),
                selectinload(Inscripcion.periodo_academico),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.materia),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.docente),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.aula),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.horario)
            )
            .where(Inscripcion.codigo_inscripcion == codigo_inscripcion)
        )

        logger.info(f"Inscripcion {codigo_inscripcion} creada con {len(detalles_creados)} detalles")
        return result.scalar_one()
    
    async def get_inscripcion_by_codigo(self, codigo_inscripcion: str) -> Optional[Inscripcion]:
        """Obtener inscripción por código"""
        result = await self.db.execute(
            select(Inscripcion)
            .options(
                selectinload(Inscripcion.estudiante),
                selectinload(Inscripcion.periodo_academico),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.materia),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.docente),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.aula),
                selectinload(Inscripcion.detalles).selectinload(DetalleInscripcion.grupo).selectinload(Grupo.horario)
            )
            .where(Inscripcion.codigo_inscripcion == codigo_inscripcion)
        )
        return result.scalar_one_or_none()
    
    async def get_inscripciones_by_estudiante(self, registro_academico: str) -> List[Dict[str, Any]]:
        """Obtener todas las inscripciones de un estudiante"""
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Inscripcion)
            .options(
                selectinload(Inscripcion.detalles)
                .selectinload(DetalleInscripcion.grupo)
                .selectinload(Grupo.materia),
                selectinload(Inscripcion.detalles)
                .selectinload(DetalleInscripcion.grupo)
                .selectinload(Grupo.docente),
                selectinload(Inscripcion.detalles)
                .selectinload(DetalleInscripcion.grupo)
                .selectinload(Grupo.aula),
                selectinload(Inscripcion.detalles)
                .selectinload(DetalleInscripcion.grupo)
                .selectinload(Grupo.horario)
            )
            .where(Inscripcion.registro_academico == registro_academico)
            .order_by(Inscripcion.fecha_inscripcion.desc())
        )
        inscripciones = result.scalars().all()

        inscripciones_dto = []
        for inscripcion in inscripciones:
            detalles = []
            for detalle in inscripcion.detalles:
                grupo = detalle.grupo
                materia = grupo.materia
                docente = grupo.docente
                aula = grupo.aula
                horario = grupo.horario
                detalles.append({
                    "codigo_detalle": detalle.codigo_detalle,
                    "grupo": {
                        "codigo_grupo": grupo.codigo_grupo,
                        "sigla_materia": grupo.sigla_materia,
                        "materia": {
                            "sigla": materia.sigla,
                            "nombre": materia.nombre,
                            "creditos": materia.creditos,
                            "es_electiva": materia.es_electiva
                        } if materia else None,
                        "descripcion": grupo.descripcion,
                        "docente": {
                            "codigo_docente": docente.codigo_docente,
                            "nombre": docente.nombre,
                            "apellido": docente.apellido
                        } if docente else None,
                        "aula": {
                            "codigo_aula": aula.codigo_aula,
                            "modulo": aula.modulo,
                            "aula": aula.aula,
                            "ubicacion": aula.ubicacion
                        } if aula else None,
                        "horario": {
                            "codigo_horario": horario.codigo_horario,
                            "dias_semana": horario.dias_semana,
                            "hora_inicio": str(horario.hora_inicio),
                            "hora_fin": str(horario.hora_fin)
                        } if horario else None,
                        "cupo": grupo.cupo,
                        "inscritos_actuales": grupo.inscritos_actuales
                    }
                })
            inscripcion_dict = {
                "codigo_inscripcion": inscripcion.codigo_inscripcion,
                "registro_academico": inscripcion.registro_academico,
                "codigo_periodo": inscripcion.codigo_periodo,
                "fecha_inscripcion": inscripcion.fecha_inscripcion,
                "detalles": detalles
            }
            inscripciones_dto.append(inscripcion_dict)

        return inscripciones_dto
    
    async def get_inscripciones_by_periodo(self, codigo_periodo: str) -> List[Dict[str, Any]]:
        """Obtener todas las inscripciones de un período"""
        result = await self.db.execute(
            select(Inscripcion)
            .where(Inscripcion.codigo_periodo == codigo_periodo)
            .order_by(Inscripcion.fecha_inscripcion.desc())
        )
        inscripciones = result.scalars().all()
        
        # Convertir a diccionarios simples
        inscripciones_dto = []
        for inscripcion in inscripciones:
            inscripcion_dict = {
                "codigo_inscripcion": inscripcion.codigo_inscripcion,
                "registro_academico": inscripcion.registro_academico,
                "codigo_periodo": inscripcion.codigo_periodo,
                "fecha_inscripcion": inscripcion.fecha_inscripcion
            }
            inscripciones_dto.append(inscripcion_dict)
        
        return inscripciones_dto
    
    async def update_inscripcion(self, codigo_inscripcion: str, inscripcion_data: InscripcionUpdate) -> Optional[Inscripcion]:
        """Actualizar una inscripción"""
        result = await self.db.execute(
            select(Inscripcion).where(Inscripcion.codigo_inscripcion == codigo_inscripcion)
        )
        inscripcion = result.scalar_one_or_none()
        
        if not inscripcion:
            return None
        
        # Actualizar campos
        for field, value in inscripcion_data.model_dump(exclude_unset=True).items():
            setattr(inscripcion, field, value)
        
        await self.db.commit()
        await self.db.refresh(inscripcion)
        
        return inscripcion
    
    async def delete_inscripcion(self, codigo_inscripcion: str) -> bool:
        """Eliminar una inscripción y sus detalles"""
        
        # Obtener la inscripción con sus detalles
        result = await self.db.execute(
            select(Inscripcion)
            .options(selectinload(Inscripcion.detalles))
            .where(Inscripcion.codigo_inscripcion == codigo_inscripcion)
        )
        inscripcion = result.scalar_one_or_none()
        
        if not inscripcion:
            return False
        
        # Decrementar contadores de grupos
        for detalle in inscripcion.detalles:
            await self._decrement_grupo_inscritos(detalle.codigo_grupo)
        
        # Eliminar detalles
        for detalle in inscripcion.detalles:
            await self.db.delete(detalle)
        
        # Eliminar inscripción
        await self.db.delete(inscripcion)
        await self.db.commit()
        
        return True
    
    async def add_grupo_to_inscripcion(self, codigo_inscripcion: str, codigo_grupo: str) -> Optional[DetalleInscripcion]:
        """Agregar un grupo a una inscripción existente"""
        
        # Verificar que la inscripción existe
        inscripcion = await self.get_inscripcion_by_codigo(codigo_inscripcion)
        if not inscripcion:
            raise InscripcionNoEncontradaException(codigo_inscripcion)
        logger.info(f"Agregar grupo {codigo_grupo} a inscripcion {codigo_inscripcion}")
        # Verificar que el grupo no esté ya inscrito
        existing_detail = await self.db.execute(
            select(DetalleInscripcion).where(
                and_(
                    DetalleInscripcion.codigo_inscripcion == codigo_inscripcion,
                    DetalleInscripcion.codigo_grupo == codigo_grupo
                )
            )
        )
        if existing_detail.scalar_one_or_none():
            logger.warning(f"Grupo duplicado {codigo_grupo} para inscripcion {codigo_inscripcion}")
            raise GrupoDuplicadoException(
                inscripcion.registro_academico,
                codigo_grupo,
                inscripcion.codigo_periodo
            )

        # Validar disponibilidad del grupo
        await self._validate_grupos_disponibilidad([codigo_grupo])

        # Validar conflictos de horario
        grupos_actuales = [d.codigo_grupo for d in inscripcion.detalles]
        grupos_actuales.append(codigo_grupo)
        await self._validate_horarios_conflicto(grupos_actuales)

        # Crear el detalle
        codigo_detalle = f"D{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
        nuevo_detalle = DetalleInscripcion(
            codigo_detalle=codigo_detalle,
            codigo_inscripcion=codigo_inscripcion,
            codigo_grupo=codigo_grupo
        )

        self.db.add(nuevo_detalle)
        await self._increment_grupo_inscritos(codigo_grupo)
        logger.info(f"Incrementado inscritos para grupo {codigo_grupo} (add)")
        await self.db.commit()
        logger.info(f"Detalle {codigo_detalle} agregado a inscripcion {codigo_inscripcion}")
        return nuevo_detalle
    
    async def remove_grupo_from_inscripcion(self, codigo_inscripcion: str, codigo_grupo: str) -> bool:
        """Remover un grupo de una inscripción"""
        
        result = await self.db.execute(
            select(DetalleInscripcion).where(
                and_(
                    DetalleInscripcion.codigo_inscripcion == codigo_inscripcion,
                    DetalleInscripcion.codigo_grupo == codigo_grupo
                )
            )
        )
        detalle = result.scalar_one_or_none()
        
        if not detalle:
            logger.warning(f"Detalle no encontrado para inscripcion {codigo_inscripcion} y grupo {codigo_grupo}")
            return False

        await self.db.delete(detalle)
        await self._decrement_grupo_inscritos(codigo_grupo)
        logger.info(f"Decrementado inscritos para grupo {codigo_grupo} (remove)")
        await self.db.commit()
        logger.info(f"Grupo {codigo_grupo} removido de inscripcion {codigo_inscripcion}")
        return True
    
    async def get_estadisticas_inscripcion(self) -> EstadisticasInscripcion:
        """Obtener estadísticas de inscripciones"""
        
        # Total inscripciones
        total_inscripciones = await self.db.scalar(select(func.count(Inscripcion.codigo_inscripcion)))
        
        # Inscripciones por período
        result = await self.db.execute(
            select(
                PeriodoAcademico.semestre,
                func.count(Inscripcion.codigo_inscripcion).label('total')
            )
            .outerjoin(Inscripcion)
            .group_by(PeriodoAcademico.semestre)
        )
        inscripciones_por_periodo = {row.semestre: row.total for row in result}
        
        # Estudiantes activos
        estudiantes_activos = await self.db.scalar(
            select(func.count(Estudiante.registro_academico))
            .where(Estudiante.estado_academico == 'REGULAR')
        )
        
        # Grupos disponibles
        grupos_disponibles = await self.db.scalar(
            select(func.count(Grupo.codigo_grupo))
            .where(Grupo.inscritos_actuales < Grupo.cupo)
        )
        
        return EstadisticasInscripcion(
            total_inscripciones=total_inscripciones or 0,
            inscripciones_por_periodo=inscripciones_por_periodo,
            estudiantes_activos=estudiantes_activos or 0,
            grupos_disponibles=grupos_disponibles or 0
        )
    
    # Métodos auxiliares privados
    async def get_estudiante_by_registro(self, registro_academico: str) -> Optional[Estudiante]:
        """Obtener estudiante por registro académico"""
        result = await self.db.execute(
            select(Estudiante).where(Estudiante.registro_academico == registro_academico)
        )
        return result.scalar_one_or_none()
    
    async def get_periodo_by_codigo(self, codigo_periodo: str) -> Optional[PeriodoAcademico]:
        """Obtener período académico por código"""
        result = await self.db.execute(
            select(PeriodoAcademico).where(PeriodoAcademico.codigo_periodo == codigo_periodo)
        )
        return result.scalar_one_or_none()
    
    async def _validate_grupos_disponibilidad(self, codigos_grupos: List[str]):
        """Validar que los grupos tengan cupo disponible"""
        for codigo_grupo in codigos_grupos:
            result = await self.db.execute(
                select(Grupo).where(Grupo.codigo_grupo == codigo_grupo)
            )
            grupo = result.scalar_one_or_none()
            
            if not grupo:
                raise GrupoNoEncontradoException(codigo_grupo)
            
            if grupo.inscritos_actuales >= grupo.cupo:
                raise GrupoSinCupoException(
                    codigo_grupo,
                    grupo.cupo,
                    grupo.inscritos_actuales
                )
    
    async def _validate_horarios_conflicto(self, codigos_grupos: List[str]):
        """Validar que no haya conflictos de horarios entre grupos"""
        result = await self.db.execute(
            select(Grupo, Horario)
            .join(Horario)
            .where(Grupo.codigo_grupo.in_(codigos_grupos))
        )
        
        grupos_horarios = [(grupo, horario) for grupo, horario in result]
        
        # Verificar conflictos
        for i, (grupo1, horario1) in enumerate(grupos_horarios):
            for j, (grupo2, horario2) in enumerate(grupos_horarios):
                if i >= j:
                    continue
                
                # Verificar si hay días en común
                dias_comunes = set(horario1.dias_semana) & set(horario2.dias_semana)
                if not dias_comunes:
                    continue
                
                # Verificar solapamiento de horarios
                if self._horarios_se_solapan(horario1.hora_inicio, horario1.hora_fin, 
                                           horario2.hora_inicio, horario2.hora_fin):
                    raise ConflictoHorarioException(
                        grupo1.codigo_grupo,
                        grupo2.codigo_grupo,
                        list(dias_comunes),
                        f"{horario1.hora_inicio}-{horario1.hora_fin} vs {horario2.hora_inicio}-{horario2.hora_fin}"
                    )
    
    def _horarios_se_solapan(self, inicio1, fin1, inicio2, fin2) -> bool:
        """Verificar si dos horarios se solapan"""
        return not (fin1 <= inicio2 or fin2 <= inicio1)
    
    async def _increment_grupo_inscritos(self, codigo_grupo: str):
        """Incrementar el contador de inscritos de un grupo"""
        result = await self.db.execute(
            select(Grupo).where(Grupo.codigo_grupo == codigo_grupo)
        )
        grupo = result.scalar_one()
        grupo.inscritos_actuales += 1
    
    async def _decrement_grupo_inscritos(self, codigo_grupo: str):
        """Decrementar el contador de inscritos de un grupo"""
        result = await self.db.execute(
            select(Grupo).where(Grupo.codigo_grupo == codigo_grupo)
        )
        grupo = result.scalar_one()
        grupo.inscritos_actuales = max(0, grupo.inscritos_actuales - 1)

class PeriodoAcademicoService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_periodo(self, periodo_data: PeriodoAcademicoCreate) -> PeriodoAcademico:
        """Crear un nuevo período académico"""
        nuevo_periodo = PeriodoAcademico(**periodo_data.model_dump())
        self.db.add(nuevo_periodo)
        await self.db.commit()
        await self.db.refresh(nuevo_periodo)
        return nuevo_periodo
    
    async def get_periodo_activo(self) -> Optional[PeriodoAcademico]:
        """Obtener el período académico activo"""
        result = await self.db.execute(
            select(PeriodoAcademico).where(PeriodoAcademico.estado == "ACTIVO")
        )
        return result.scalar_one_or_none()
    
    async def get_all_periodos(self) -> List[PeriodoAcademico]:
        """Obtener todos los períodos académicos"""
        result = await self.db.execute(select(PeriodoAcademico))
        return result.scalars().all()
