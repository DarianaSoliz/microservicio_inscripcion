import asyncio
import concurrent.futures
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from celery import current_task
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.celery_app import celery_app
from app.core.database import get_db, AsyncSessionLocal
from app.core.config import settings
from app.models import DetalleInscripcion, Grupo, Inscripcion, PeriodoAcademico, Estudiante, Horario
from app.schemas import InscripcionCreate

# Enhanced imports for new functionality (temporarily disabled to fix serialization)
# from app.circuit_breaker import CircuitBreaker, circuit_breaker_registry, database_circuit_breaker, circuit_breaker
# from app.idempotency import IdempotencyManager, InscriptionIdempotency, idempotency_manager, inscription_idempotency
# from app.saga_pattern import SagaTransaction, InscriptionSagaOrchestrator, saga_manager
# from app.enhanced_logging import StructuredLogger, CorrelationManager, structured_logger

# Alias for easier usage (using standard logging for now)
import logging
logger = logging.getLogger(__name__)

# Database session helper (not currently used but keeping for future use)
async def get_db_session():
    """Get database session - wrapper for async session"""
    session = AsyncSessionLocal()
    try:
        return session
    finally:
        await session.close()

# Helper functions for group management
async def _decrement_grupo_inscritos(db: AsyncSession, codigo_grupo: str) -> None:
    """Decrement the number of enrolled students in a group"""
    try:
        result = await db.execute(
            select(Grupo).where(Grupo.codigo_grupo == codigo_grupo).with_for_update()
        )
        grupo = result.scalar_one_or_none()

        if grupo and getattr(grupo, 'inscritos_actuales', None) is not None and grupo.inscritos_actuales > 0:
            grupo.inscritos_actuales = grupo.inscritos_actuales - 1
            await db.flush()
    except Exception as e:
        logger.warning(f"Error decrementing group enrollment: {str(e)}")

async def _increment_grupo_inscritos(db: AsyncSession, codigo_grupo: str) -> None:
    """Increment the number of enrolled students in a group"""
    try:
        result = await db.execute(
            select(Grupo).where(Grupo.codigo_grupo == codigo_grupo).with_for_update()
        )
        grupo = result.scalar_one_or_none()

        if grupo:
            if getattr(grupo, 'inscritos_actuales', None) is None:
                grupo.inscritos_actuales = 1
            else:
                grupo.inscritos_actuales = grupo.inscritos_actuales + 1
            await db.flush()
    except Exception as e:
        logger.warning(f"Error incrementing group enrollment: {str(e)}")

# Helper para ejecutar funciones async en un subproceso y evitar conflicto de event loop
def run_async_in_process(func, *args, **kwargs):
    """Run async function in a thread pool to avoid event loop issues"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # Create a closure that properly runs the coroutine
        def run_in_thread():
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the coroutine
            return loop.run_until_complete(func(*args, **kwargs))
        
        # Execute in thread and wait for result
        future = executor.submit(run_in_thread)
        result = future.result()  # This blocks until result is available
        return result

# Helper para ejecutar funciones async correctamente según el estado del event loop
def run_async(func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Si ya hay un loop, ejecuta la función en el loop actual
        coro = func(*args, **kwargs)
        fut = asyncio.ensure_future(coro)
        # Si se llama desde sync, se debe esperar el resultado
        # pero en Celery estándar esto no es lo ideal, así que solo retorna el resultado si ya está terminado
        # Si no, lanza excepción clara
        if fut.done():
            return fut.result()
        else:
            raise RuntimeError("No se puede ejecutar función async en un loop ya corriendo desde sync. Usa await en workers async.")
    else:
        return asyncio.run(func(*args, **kwargs))

# Import exceptions
from app.exceptions import (
    EstudianteNoEncontradoException,
    EstudianteBloqueadoException,
    PeriodoNoEncontradoException,
    PeriodoInactivoException,
    GrupoNoEncontradoException,
    GrupoSinCupoException,
    ConflictoHorarioException,
    InscripcionDuplicadaException,
    GrupoDuplicadoException
)

# Configurar motor de base de datos para las tareas
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@celery_app.task(name="app.tasks.create_inscription_task")
def create_inscription_task(inscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """Task for creating a single inscription"""
    try:
        result = run_async_in_process(_create_inscription_async, inscription_data)
        return {
            "status": "SUCCESS",
            "data": result
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)
        }

@celery_app.task(bind=True, name="app.tasks.bulk_create_inscriptions_task")

@celery_app.task(bind=True, name="app.tasks.bulk_create_inscriptions_task")
def bulk_create_inscriptions_task(self, inscriptions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tarea para crear múltiples inscripciones en lote"""
    try:
        total_inscriptions = len(inscriptions_data)
        processed = 0
        successful = 0
        failed = 0
        results = []
        if hasattr(self, 'request') and getattr(self.request, 'id', None):
            self.update_state(
                state="STARTED", 
                meta={
                    "message": f"Procesando {total_inscriptions} inscripciones...",
                    "total": total_inscriptions,
                    "processed": 0,
                    "successful": 0,
                    "failed": 0
                }
            )
        for i, inscription_data in enumerate(inscriptions_data):
            try:
                result = run_async_in_process(_create_inscription_async, inscription_data, self)
                results.append({
                    "status": "success",
                    "data": result,
                    "registro_academico": inscription_data.get("registro_academico")
                })
                successful += 1
            except Exception as e:
                results.append({
                    "status": "error",
                    "error": str(e),
                    "registro_academico": inscription_data.get("registro_academico")
                })
                failed += 1
            processed += 1
            if processed % 5 == 0 or processed == total_inscriptions:
                if hasattr(self, 'request') and getattr(self.request, 'id', None):
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "message": f"Procesadas {processed}/{total_inscriptions} inscripciones",
                            "total": total_inscriptions,
                            "processed": processed,
                            "successful": successful,
                            "failed": failed,
                            "progress": int((processed / total_inscriptions) * 100)
                        }
                    )
        return {
            "status": "SUCCESS",
            "message": f"Procesamiento completado: {successful} exitosas, {failed} fallidas",
            "total": total_inscriptions,
            "successful": successful,
            "failed": failed,
            "results": results
        }
    except Exception as exc:
        if hasattr(self, 'request') and getattr(self.request, 'id', None):
            self.update_state(
                state="FAILURE",
                meta={
                    "message": f"Error en procesamiento en lote: {str(exc)}",
                    "error": str(exc)
                }
            )
        raise exc

# Removed problematic saga function - using simplified version later in file

# Removed the circuit_breaker decorator that was causing issues
async def _create_inscription_async(inscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """Función auxiliar para crear inscripción de forma asíncrona"""
    
    # Inicializar motor y sesión dentro del subproceso para evitar problemas de event loop
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
        pool_pre_ping=True
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as db:
        try:
            # Verificar que el estudiante existe y no esté bloqueado
            result = await db.execute(
                select(Estudiante).where(Estudiante.registro_academico == inscription_data["registro_academico"])
            )
            estudiante = result.scalar_one_or_none()
            
            if not estudiante:
                raise EstudianteNoEncontradoException(inscription_data["registro_academico"])
            
            if estudiante.estado_academico == "BLOQUEADO":
                raise EstudianteBloqueadoException(inscription_data["registro_academico"])
            
            # Verificar que el período académico existe y está activo
            result = await db.execute(
                select(PeriodoAcademico).where(PeriodoAcademico.codigo_periodo == inscription_data["codigo_periodo"])
            )
            periodo = result.scalar_one_or_none()
            
            if not periodo:
                raise PeriodoNoEncontradoException(inscription_data["codigo_periodo"])
            
            if periodo.estado != "ACTIVO":
                raise PeriodoInactivoException(inscription_data["codigo_periodo"], periodo.estado)
            
            # Obtener grupos a inscribir
            grupos = inscription_data.get("grupos", [])
            
            # Buscar inscripción existente para este estudiante y período
            result = await db.execute(
                select(Inscripcion).where(
                    and_(
                        Inscripcion.registro_academico == inscription_data["registro_academico"],
                        Inscripcion.codigo_periodo == inscription_data["codigo_periodo"]
                    )
                )
            )
            inscripcion = result.scalar_one_or_none()
            
            if inscripcion:
                # Inscripción existe, agregar solo grupos nuevos
                codigo_inscripcion = inscripcion.codigo_inscripcion
                detalles_creados = []
                
                # Obtener grupos ya inscritos en esta inscripción
                result_detalles = await db.execute(
                    select(DetalleInscripcion.codigo_grupo).where(
                        DetalleInscripcion.codigo_inscripcion == codigo_inscripcion
                    )
                )
                grupos_ya_inscritos = [row[0] for row in result_detalles]
                
                # Filtrar grupos que ya están inscritos
                grupos_nuevos = [g for g in grupos if g not in grupos_ya_inscritos]
                
                if not grupos_nuevos:
                    # Todos los grupos ya están inscritos
                    result_detalles = await db.execute(
                        select(DetalleInscripcion).where(
                            DetalleInscripcion.codigo_inscripcion == codigo_inscripcion
                        )
                    )
                    detalles = result_detalles.scalars().all()
                    return {
                        "codigo_inscripcion": codigo_inscripcion,
                        "registro_academico": inscription_data["registro_academico"],
                        "codigo_periodo": inscription_data["codigo_periodo"],
                        "fecha_inscripcion": inscripcion.fecha_inscripcion.isoformat(),
                        "detalles": [
                            {
                                "codigo_detalle": d.codigo_detalle,
                                "codigo_grupo": d.codigo_grupo
                            }
                            for d in detalles
                        ],
                        "mensaje": "Todos los grupos ya estaban inscritos"
                    }
                
                # Validar disponibilidad de nuevos grupos
                await _validate_grupos_disponibilidad(db, grupos_nuevos)
                # Validar conflictos entre nuevos grupos
                await _validate_horarios_conflicto(db, grupos_nuevos)
                # Validar conflictos con grupos ya inscritos
                await _validate_horarios_conflicto_with_existing(db, inscription_data["registro_academico"], grupos_nuevos)
                
                # Validar que los nuevos grupos no sean de materias ya inscritas
                result_materias_existentes = await db.execute(
                    select(Grupo.sigla_materia)
                    .select_from(DetalleInscripcion)
                    .join(Grupo, DetalleInscripcion.codigo_grupo == Grupo.codigo_grupo)
                    .where(DetalleInscripcion.codigo_inscripcion == codigo_inscripcion)
                )
                materias_existentes = [row[0] for row in result_materias_existentes]
                
                # Obtener materias de los nuevos grupos
                result_nuevas_materias = await db.execute(
                    select(Grupo.codigo_grupo, Grupo.sigla_materia).where(
                        Grupo.codigo_grupo.in_(grupos_nuevos)
                    )
                )
                
                for codigo_grupo, sigla_materia in result_nuevas_materias:
                    if sigla_materia in materias_existentes:
                        raise GrupoDuplicadoException(
                            codigo_grupo,
                            f"Materia {sigla_materia} ya está inscrita en este período",
                            codigo_grupo
                        )
                
                # Agregar los nuevos grupos
                for codigo_grupo in grupos_nuevos:
                    codigo_detalle = f"D{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
                    
                    detalle = DetalleInscripcion(
                        codigo_detalle=codigo_detalle,
                        codigo_inscripcion=codigo_inscripcion,
                        codigo_grupo=codigo_grupo
                    )
                    
                    db.add(detalle)
                    detalles_creados.append({
                        "codigo_detalle": codigo_detalle,
                        "codigo_grupo": codigo_grupo
                    })
                    
                    # Actualizar contador de inscritos en el grupo
                    await _increment_grupo_inscritos(db, codigo_grupo)
                
                await db.commit()
                
                return {
                    "codigo_inscripcion": codigo_inscripcion,
                    "registro_academico": inscription_data["registro_academico"],
                    "codigo_periodo": inscription_data["codigo_periodo"],
                    "fecha_inscripcion": inscripcion.fecha_inscripcion.isoformat(),
                    "detalles": detalles_creados,
                    "mensaje": f"Se agregaron {len(detalles_creados)} nuevos grupos a inscripción existente"
                }
            else:
                # Crear nueva inscripción
                codigo_inscripcion = f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
                
                # Validar grupos y disponibilidad
                await _validate_grupos_disponibilidad(db, grupos)
                # Validar conflictos entre nuevos grupos
                await _validate_horarios_conflicto(db, grupos)
                # Validar conflictos con grupos ya inscritos
                await _validate_horarios_conflicto_with_existing(db, inscription_data["registro_academico"], grupos)
                
                # Validar que no haya duplicados de materia
                await _validate_no_duplicate_materias(db, grupos)
                
                # Crear la inscripción
                nueva_inscripcion = Inscripcion(
                    codigo_inscripcion=codigo_inscripcion,
                    registro_academico=inscription_data["registro_academico"],
                    codigo_periodo=inscription_data["codigo_periodo"],
                    fecha_inscripcion=date.today()
                )
                
                db.add(nueva_inscripcion)
                await db.flush()
                
                # Crear los detalles de inscripción
                detalles_creados = []
                for codigo_grupo in grupos:
                    codigo_detalle = f"D{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
                    
                    detalle = DetalleInscripcion(
                        codigo_detalle=codigo_detalle,
                        codigo_inscripcion=codigo_inscripcion,
                        codigo_grupo=codigo_grupo
                    )
                    
                    db.add(detalle)
                    detalles_creados.append({
                        "codigo_detalle": codigo_detalle,
                        "codigo_grupo": codigo_grupo
                    })
                    
                    # Actualizar contador de inscritos en el grupo
                    await _increment_grupo_inscritos(db, codigo_grupo)
                
                await db.commit()
                
                return {
                    "codigo_inscripcion": codigo_inscripcion,
                    "registro_academico": inscription_data["registro_academico"],
                    "codigo_periodo": inscription_data["codigo_periodo"],
                    "fecha_inscripcion": date.today().isoformat(),
                    "detalles": detalles_creados
                }
            
        except Exception as e:
            await db.rollback()
            raise e

async def _validate_grupos_disponibilidad(db: AsyncSession, codigos_grupos: List[str]):
    """Validar que los grupos tengan cupo disponible"""
    # Usar SELECT ... FOR UPDATE para bloquear la fila del grupo y evitar sobre-inscripción
    for codigo_grupo in codigos_grupos:
        result = await db.execute(
            select(Grupo).where(Grupo.codigo_grupo == codigo_grupo).with_for_update()
        )
        grupo = result.scalar_one_or_none()
        if not grupo:
            raise GrupoNoEncontradoException(codigo_grupo)
        if grupo.inscritos_actuales >= grupo.cupo:
            raise GrupoSinCupoException(codigo_grupo, grupo.cupo, grupo.inscritos_actuales)

async def _validate_horarios_conflicto(db: AsyncSession, codigos_grupos: List[str]):
    """Validar que no haya conflictos de horarios entre grupos"""
    # Obtener horarios de todos los grupos
    result = await db.execute(
        select(Grupo, Horario)
        .join(Horario)
        .where(Grupo.codigo_grupo.in_(codigos_grupos))
    )

    rows = result.all()
    grupos_horarios = [(row[0], row[1]) for row in rows]
    
    # Verificar conflictos entre todos los grupos
    for i, (grupo1, horario1) in enumerate(grupos_horarios):
        for j, (grupo2, horario2) in enumerate(grupos_horarios):
            if i >= j:
                continue
            
            # Verificar si hay días en común
            dias_comunes = set(horario1.dias_semana) & set(horario2.dias_semana)
            if not dias_comunes:
                continue
            
            # Verificar solapamiento de horarios
            if _horarios_se_solapan(horario1.hora_inicio, horario1.hora_fin, 
                                   horario2.hora_inicio, horario2.hora_fin):
                raise ConflictoHorarioException(
                    grupo2.codigo_grupo,
                    f"{horario2.dias_semana} {horario2.hora_inicio}-{horario2.hora_fin}"
                )


async def _validate_horarios_conflicto_with_existing(db: AsyncSession, registro_academico: str, codigos_grupos_nuevos: List[str]):
    """Validar que los nuevos grupos no tengan conflictos con grupos ya inscritos por el estudiante"""
    
    # Obtener todos los grupos ya inscritos del estudiante en períodos ACTIVOS
    result = await db.execute(
        select(DetalleInscripcion.codigo_grupo)
        .join(Inscripcion)
        .join(PeriodoAcademico, Inscripcion.codigo_periodo == PeriodoAcademico.codigo_periodo)
        .where(
            and_(
                Inscripcion.registro_academico == registro_academico,
                PeriodoAcademico.estado == "ACTIVO"
            )
        )
    )
    grupos_existentes = [row[0] for row in result]
    
    if not grupos_existentes:
        return  # No hay grupos existentes, sin conflictos posibles
    
    # Obtener todos los horarios (nuevos + existentes)
    todos_grupos = grupos_existentes + codigos_grupos_nuevos
    result = await db.execute(
        select(Grupo, Horario)
        .join(Horario)
        .where(Grupo.codigo_grupo.in_(todos_grupos))
    )

    rows = result.all()
    grupos_horarios = [(row[0], row[1]) for row in rows]
    
    # Crear mapeo de grupos existentes para identificarlos
    existentes_set = set(grupos_existentes)
    nuevos_set = set(codigos_grupos_nuevos)
    
    # Verificar conflictos entre nuevos y existentes
    for grupo_nuevo, horario_nuevo in grupos_horarios:
        if grupo_nuevo.codigo_grupo not in nuevos_set:
            continue  # Skip si no es grupo nuevo
        
        for grupo_existente, horario_existente in grupos_horarios:
            if grupo_existente.codigo_grupo not in existentes_set:
                continue  # Skip si no es grupo existente
            
            # Verificar si hay días en común
            dias_comunes = set(horario_nuevo.dias_semana) & set(horario_existente.dias_semana)
            if not dias_comunes:
                continue
            
            # Verificar solapamiento de horarios
            if _horarios_se_solapan(horario_nuevo.hora_inicio, horario_nuevo.hora_fin,
                                   horario_existente.hora_inicio, horario_existente.hora_fin):
                raise ConflictoHorarioException(
                    grupo_nuevo.codigo_grupo,
                    f"Conflicto con grupo existente {grupo_existente.codigo_grupo}: "
                    f"{horario_existente.dias_semana} {horario_existente.hora_inicio}-{horario_existente.hora_fin}"
                )

async def _validate_horario_conflicto_individual(db: AsyncSession, registro_academico: str, 
                                               codigo_periodo: str, nuevo_grupo_codigo: str):
    """Validar que el nuevo grupo no tenga conflictos con grupos ya inscritos del estudiante"""
    
    # Obtener todos los grupos ya inscritos del estudiante en TODOS los períodos ACTIVOS
    result = await db.execute(
        select(DetalleInscripcion.codigo_grupo)
        .join(Inscripcion)
        .join(PeriodoAcademico, Inscripcion.codigo_periodo == PeriodoAcademico.codigo_periodo)
        .where(
            and_(
                Inscripcion.registro_academico == registro_academico,
                PeriodoAcademico.estado == "ACTIVO"  # Solo períodos activos
            )
        )
    )
    grupos_existentes = [row[0] for row in result]
    
    if not grupos_existentes:
        return  # No hay grupos existentes, no puede haber conflictos
    
    # Obtener horarios del nuevo grupo y grupos existentes
    todos_los_grupos = grupos_existentes + [nuevo_grupo_codigo]
    result = await db.execute(
        select(Grupo, Horario)
        .join(Horario)
        .where(Grupo.codigo_grupo.in_(todos_los_grupos))
    )

    rows = result.all()
    grupos_horarios = [(row[0], row[1]) for row in rows]
    
    # Encontrar el horario del nuevo grupo
    nuevo_grupo_horario = None
    for grupo, horario in grupos_horarios:
        if grupo.codigo_grupo == nuevo_grupo_codigo:
            nuevo_grupo_horario = (grupo, horario)
            break
    
    if not nuevo_grupo_horario:
        raise GrupoNoEncontradoException(nuevo_grupo_codigo)
    
    # Verificar conflictos con grupos existentes
    nuevo_grupo, nuevo_horario = nuevo_grupo_horario
    for grupo, horario in grupos_horarios:
        if grupo.codigo_grupo == nuevo_grupo_codigo:
            continue  # Skip self
        
        # Verificar si hay días en común
        dias_comunes = set(nuevo_horario.dias_semana) & set(horario.dias_semana)
        if not dias_comunes:
            continue
        
        # Verificar solapamiento de horarios
        if _horarios_se_solapan(nuevo_horario.hora_inicio, nuevo_horario.hora_fin, 
                               horario.hora_inicio, horario.hora_fin):
            raise ConflictoHorarioException(
                grupo.codigo_grupo,
                f"{horario.dias_semana} {horario.hora_inicio}-{horario.hora_fin}"
            )

def _horarios_se_solapan(inicio1, fin1, inicio2, fin2) -> bool:
    """Verificar si dos horarios se solapan"""
    return not (fin1 <= inicio2 or fin2 <= inicio1)

async def _validate_no_duplicate_materias(db: AsyncSession, codigos_grupos: List[str]):
    """Validar que no haya dos grupos de la misma materia"""
    # Obtener la materia de cada grupo
    result = await db.execute(
        select(Grupo.codigo_grupo, Grupo.sigla_materia).where(
            Grupo.codigo_grupo.in_(codigos_grupos)
        )
    )
    
    grupos_materias = result.all()
    materias_vistas = {}
    
    for codigo_grupo, sigla_materia in grupos_materias:
        if sigla_materia in materias_vistas:
            # La materia ya está en otro grupo
            raise GrupoDuplicadoException(
                codigo_grupo,
                f"Materia {sigla_materia} ya está incluida en grupo {materias_vistas[sigla_materia]}",
                codigo_grupo
            )
        materias_vistas[sigla_materia] = codigo_grupo

async def _increment_grupo_inscritos(db: AsyncSession, codigo_grupo: str):
    """Incrementar el contador de inscritos de un grupo"""
    # Usar SELECT ... FOR UPDATE para asegurar que el incremento sea atómico
    result = await db.execute(
        select(Grupo).where(Grupo.codigo_grupo == codigo_grupo).with_for_update()
    )
    grupo = result.scalar_one()
    grupo.inscritos_actuales += 1


@celery_app.task(name="app.tasks.create_single_group_inscription_task", bind=True)
def create_single_group_inscription_task(self, inscription_data: Dict[str, Any], grupo_codigo: str) -> Dict[str, Any]:
    """Tarea para inscribir un grupo específico, con manejo de concurrencia y errores mejorado"""
    if hasattr(self, 'request') and getattr(self.request, 'id', None):
        self.update_state(
            state="PROGRESS",
            meta={
                "message": f"Procesando inscripción para grupo {grupo_codigo}...",
                "grupo": grupo_codigo,
                "registro_academico": inscription_data.get("registro_academico")
            }
        )
    single_group_data = inscription_data.copy()
    single_group_data["grupos"] = [grupo_codigo]
    try:
        # Ejecutar la función async en subproceso, sin pasar self
        result = run_async_in_process(_add_group_to_inscription_async, inscription_data, grupo_codigo)
        if hasattr(self, 'request') and getattr(self.request, 'id', None):
            self.update_state(
                state="SUCCESS",
                meta={
                    "message": f"Inscripción para grupo {grupo_codigo} creada exitosamente",
                    "grupo": grupo_codigo,
                    "registro_academico": inscription_data.get("registro_academico")
                }
            )
        return {
            "status": "SUCCESS",
            "message": f"Inscripción para grupo {grupo_codigo} creada exitosamente",
            "grupo": grupo_codigo,
            "data": result
        }
    except GrupoDuplicadoException as exc:
        return {
            "status": "ERROR",
            "message": f"El estudiante ya está inscrito en el grupo {grupo_codigo} en el periodo {inscription_data.get('codigo_periodo')}",
            "error": str(exc)
        }
    except EstudianteNoEncontradoException as exc:
        return {
            "status": "ERROR",
            "message": f"Estudiante no encontrado: {inscription_data.get('registro_academico')}",
            "error": str(exc)
        }
    except EstudianteBloqueadoException as exc:
        return {
            "status": "ERROR",
            "message": f"Estudiante bloqueado: {inscription_data.get('registro_academico')}",
            "error": str(exc)
        }
    except PeriodoNoEncontradoException as exc:
        return {
            "status": "ERROR",
            "message": f"Periodo académico no encontrado: {inscription_data.get('codigo_periodo')}",
            "error": str(exc)
        }
    except PeriodoInactivoException as exc:
        return {
            "status": "ERROR",
            "message": f"Periodo académico inactivo: {inscription_data.get('codigo_periodo')}",
            "error": str(exc)
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": f"Error inesperado al inscribir grupo {grupo_codigo}",
            "error": str(exc)
        }

async def _add_group_to_inscription_async(inscription_data: Dict[str, Any], grupo_codigo: str) -> Dict[str, Any]:
    """Función auxiliar para agregar un grupo a una inscripción (crear inscripción si no existe)"""
    
    # Inicializar motor y sesión dentro del subproceso para evitar problemas de event loop
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
        pool_pre_ping=True
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with AsyncSessionLocal() as db:
        try:
            # Generar código único para la inscripción (si no existe)
            codigo_inscripcion = inscription_data.get("codigo_inscripcion")
            if not codigo_inscripcion:
                codigo_inscripcion = f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
            
            # Validar que el estudiante existe
            result = await db.execute(
                select(Estudiante).where(Estudiante.registro_academico == inscription_data["registro_academico"])
            )
            estudiante = result.scalar_one_or_none()
            if not estudiante:
                raise EstudianteNoEncontradoException(inscription_data["registro_academico"])
            if estudiante.estado_academico == "BLOQUEADO":
                raise EstudianteBloqueadoException(inscription_data["registro_academico"])
            
            # Validar que el período existe
            result = await db.execute(
                select(PeriodoAcademico).where(PeriodoAcademico.codigo_periodo == inscription_data["codigo_periodo"])
            )
            periodo = result.scalar_one_or_none()
            if not periodo:
                raise PeriodoNoEncontradoException(inscription_data["codigo_periodo"])
            if periodo.estado != "ACTIVO":
                raise PeriodoInactivoException(inscription_data["codigo_periodo"], periodo.estado)
            
            # Validar que el grupo tiene cupo disponible
            await _validate_grupos_disponibilidad(db, [grupo_codigo])

            # Validar que el estudiante no esté inscrito en otro grupo de la misma materia en este periodo
            # Obtener la materia del grupo actual
            grupo_result = await db.execute(
                select(Grupo).where(Grupo.codigo_grupo == grupo_codigo)
            )
            grupo_actual = grupo_result.scalar_one_or_none()
            if not grupo_actual:
                raise GrupoNoEncontradoException(grupo_codigo)

            materia_actual = grupo_actual.sigla_materia

            # Buscar todas las materias inscritas por el estudiante en el periodo
            grupos_inscritos_result = await db.execute(
                select(Grupo.sigla_materia)
                .select_from(DetalleInscripcion)
                .join(Inscripcion, DetalleInscripcion.codigo_inscripcion == Inscripcion.codigo_inscripcion)
                .join(Grupo, DetalleInscripcion.codigo_grupo == Grupo.codigo_grupo)
                .where(
                    and_(
                        Inscripcion.registro_academico == inscription_data["registro_academico"],
                        Inscripcion.codigo_periodo == inscription_data["codigo_periodo"]
                    )
                )
            )
            materias_inscritas = [row[0] for row in grupos_inscritos_result]
            if materia_actual in materias_inscritas:
                raise GrupoDuplicadoException(
                    inscription_data["registro_academico"],
                    grupo_codigo,
                    inscription_data["codigo_periodo"]
                )

            # Validar conflictos de horarios con grupos ya inscritos del estudiante
            await _validate_horario_conflicto_individual(db, inscription_data["registro_academico"], 
                                                       inscription_data["codigo_periodo"], grupo_codigo)

            # Validar que el estudiante no esté ya inscrito en este grupo en este período
            existing_group_inscription = await db.execute(
                select(DetalleInscripcion)
                .join(Inscripcion)
                .where(
                    and_(
                        Inscripcion.registro_academico == inscription_data["registro_academico"],
                        Inscripcion.codigo_periodo == inscription_data["codigo_periodo"],
                        DetalleInscripcion.codigo_grupo == grupo_codigo
                    )
                )
            )
            if existing_group_inscription.scalar_one_or_none():
                raise GrupoDuplicadoException(
                    inscription_data["registro_academico"],
                    grupo_codigo,
                    inscription_data["codigo_periodo"]
                )
            
            # Buscar o crear la inscripción principal
            result = await db.execute(
                select(Inscripcion).where(
                    and_(
                        Inscripcion.registro_academico == inscription_data["registro_academico"],
                        Inscripcion.codigo_periodo == inscription_data["codigo_periodo"]
                    )
                )
            )
            inscripcion = result.scalar_one_or_none()
            
            if not inscripcion:
                # Crear nueva inscripción
                inscripcion = Inscripcion(
                    codigo_inscripcion=codigo_inscripcion,
                    registro_academico=inscription_data["registro_academico"],
                    codigo_periodo=inscription_data["codigo_periodo"],
                    fecha_inscripcion=date.today()
                )
                db.add(inscripcion)
                await db.flush()
            else:
                codigo_inscripcion = inscripcion.codigo_inscripcion
            
            # Crear el detalle para este grupo específico
            codigo_detalle = f"D{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}"
            
            detalle = DetalleInscripcion(
                codigo_detalle=codigo_detalle,
                codigo_inscripcion=codigo_inscripcion,
                codigo_grupo=grupo_codigo
            )
            
            db.add(detalle)
            
            # Actualizar contador de inscritos en el grupo
            await _increment_grupo_inscritos(db, grupo_codigo)
            
            await db.commit()
            
            return {
                "codigo_inscripcion": codigo_inscripcion,
                "codigo_detalle": codigo_detalle,
                "grupo": grupo_codigo,
                "fecha_inscripcion": date.today().isoformat()
            }
            
        except Exception as e:
            await db.rollback()
            raise e

@celery_app.task(name="app.tasks.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """Tarea de health check para verificar que los workers están funcionando"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "worker_id": current_task.request.hostname
    }


@celery_app.task(name="app.tasks.create_enhanced_inscription_task", bind=True)
def create_enhanced_inscription_task(self, inscription_data: Dict[str, Any]) -> Dict[str, Any]:
    """Task for creating inscriptions by groups"""
    try:
        # Extract data
        registro_academico = inscription_data.get("registro_academico")
        codigo_periodo = inscription_data.get("codigo_periodo")
        grupos = inscription_data.get("grupos", [])
        
        # Update task state
        self.update_state(
            state="STARTED",
            meta={
                "message": f"Iniciando inscripción para {len(grupos)} grupos",
                "registro_academico": registro_academico,
                "codigo_periodo": codigo_periodo,
                "total_grupos": len(grupos),
                "procesados": 0
            }
        )
        
        # Process all groups in a single inscription
        result = run_async_in_process(_create_inscription_async, inscription_data)
        
        return {
            "status": "SUCCESS",
            "message": "Inscripción creada exitosamente",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error en create_enhanced_inscription_task: {str(e)}", exc_info=True)
        return {
            "status": "ERROR",
            "message": f"Error al crear inscripción: {str(e)}",
            "error": str(e)
        }


# ===== ENHANCED SAGA IMPLEMENTATION =====

async def _create_inscription_with_saga(
    inscription_data: Dict[str, Any],
    task: Optional[Any] = None,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crear inscripciones - minimal version to debug
    """
    try:
        # Extract and validate data
        registro_academico = inscription_data.get("registro_academico")
        codigo_periodo = inscription_data.get("codigo_periodo")
        grupos = inscription_data.get("grupos", [])
        
        if not all([registro_academico, codigo_periodo, grupos]):
            raise ValueError("Missing required fields")
        
        # Return simple result without database calls for now
        return {
            "success": True,
            "codigo_inscripcion": f"I{datetime.now().strftime('%y%m%d')}{str(uuid.uuid4())[:3].upper()}",
            "registro_academico": registro_academico,
            "codigo_periodo": codigo_periodo,
            "fecha_inscripcion": date.today().isoformat(),
            "detalles": [{"codigo_grupo": g, "codigo_detalle": f"D{uuid.uuid4().hex[:8]}"} for g in grupos],
            "grupos_count": len(grupos)
        }
        
    except Exception as e:
        raise e


# Note: Saga step functions removed for now to avoid serialization issues
# These can be re-implemented later with proper serialization handling
