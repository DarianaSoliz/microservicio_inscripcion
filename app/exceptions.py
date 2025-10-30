"""
Excepciones personalizadas para el sistema de inscripciones académicas.
"""

from typing import Any, Dict, Optional, List
from fastapi import status


class InscripcionBaseException(Exception):
    """Excepción base para el sistema de inscripciones"""

    def __init__(
        self,
        message: str,
        error_code: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.details = details or {}
        super().__init__(self.message)


# ===== EXCEPCIONES DE VALIDACIÓN ACADÉMICA =====


class EstudianteException(InscripcionBaseException):
    """Excepciones relacionadas con estudiantes"""
    pass


class EstudianteNoEncontradoException(EstudianteException):
    """El estudiante no existe en el sistema"""

    def __init__(self, registro_academico: str):
        super().__init__(
            message=f"Estudiante con registro académico '{registro_academico}' no encontrado",
            error_code="ESTUDIANTE_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"registro_academico": registro_academico},
        )


class EstudianteBloqueadoException(EstudianteException):
    """El estudiante está bloqueado y no puede inscribirse"""

    def __init__(self, registro_academico: str, razon_bloqueo: str = None):
        super().__init__(
            message=f"Estudiante '{registro_academico}' está bloqueado y no puede inscribirse",
            error_code="ESTUDIANTE_BLOQUEADO",
            http_status=status.HTTP_403_FORBIDDEN,
            details={
                "registro_academico": registro_academico,
                "razon_bloqueo": razon_bloqueo,
            },
        )


class EstudianteInactivoException(EstudianteException):
    """El estudiante está inactivo en el sistema"""

    def __init__(self, registro_academico: str, fecha_inactivacion: str = None):
        super().__init__(
            message=f"Estudiante '{registro_academico}' está inactivo en el sistema",
            error_code="ESTUDIANTE_INACTIVO",
            http_status=status.HTTP_403_FORBIDDEN,
            details={
                "registro_academico": registro_academico,
                "fecha_inactivacion": fecha_inactivacion,
            },
        )


class EstudianteSuspendidoException(EstudianteException):
    """El estudiante está suspendido temporalmente"""

    def __init__(self, registro_academico: str, fecha_suspension: str = None, fecha_fin_suspension: str = None):
        super().__init__(
            message=f"Estudiante '{registro_academico}' está suspendido temporalmente",
            error_code="ESTUDIANTE_SUSPENDIDO",
            http_status=status.HTTP_403_FORBIDDEN,
            details={
                "registro_academico": registro_academico,
                "fecha_suspension": fecha_suspension,
                "fecha_fin_suspension": fecha_fin_suspension,
            },
        )


class PeriodoAcademicoException(InscripcionBaseException):
    """Excepciones relacionadas con períodos académicos"""
    pass


class PeriodoNoEncontradoException(PeriodoAcademicoException):
    """El período académico no existe"""

    def __init__(self, codigo_periodo: str):
        super().__init__(
            message=f"Período académico '{codigo_periodo}' no encontrado",
            error_code="PERIODO_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"codigo_periodo": codigo_periodo},
        )


class PeriodoInactivoException(PeriodoAcademicoException):
    """El período académico no está activo"""

    def __init__(self, codigo_periodo: str, estado_actual: str):
        super().__init__(
            message=f"Período académico '{codigo_periodo}' no está activo (estado: {estado_actual})",
            error_code="PERIODO_INACTIVO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"codigo_periodo": codigo_periodo, "estado_actual": estado_actual},
        )


class PeriodoInscripcionCerradoException(PeriodoAcademicoException):
    """El período de inscripciones está cerrado"""

    def __init__(self, codigo_periodo: str, fecha_cierre: str = None):
        super().__init__(
            message=f"El período de inscripciones para '{codigo_periodo}' está cerrado",
            error_code="PERIODO_INSCRIPCION_CERRADO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_periodo": codigo_periodo,
                "fecha_cierre": fecha_cierre,
            },
        )


class PeriodoInscripcionNoIniciadoException(PeriodoAcademicoException):
    """El período de inscripciones aún no ha iniciado"""

    def __init__(self, codigo_periodo: str, fecha_inicio: str = None):
        super().__init__(
            message=f"El período de inscripciones para '{codigo_periodo}' aún no ha iniciado",
            error_code="PERIODO_INSCRIPCION_NO_INICIADO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_periodo": codigo_periodo,
                "fecha_inicio": fecha_inicio,
            },
        )


class GrupoException(InscripcionBaseException):
    """Excepciones relacionadas con grupos"""
    pass


class GrupoNoEncontradoException(GrupoException):
    """El grupo no existe"""

    def __init__(self, codigo_grupo: str):
        super().__init__(
            message=f"Grupo '{codigo_grupo}' no encontrado",
            error_code="GRUPO_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"codigo_grupo": codigo_grupo},
        )


class GrupoSinCupoException(GrupoException):
    """El grupo no tiene cupo disponible"""

    def __init__(self, codigo_grupo: str, cupo_total: int, inscritos_actuales: int):
        super().__init__(
            message=f"Grupo '{codigo_grupo}' no tiene cupo disponible ({inscritos_actuales}/{cupo_total})",
            error_code="GRUPO_SIN_CUPO",
            http_status=status.HTTP_409_CONFLICT,
            details={
                "codigo_grupo": codigo_grupo,
                "cupo_total": cupo_total,
                "inscritos_actuales": inscritos_actuales,
                "cupo_disponible": cupo_total - inscritos_actuales,
            },
        )


class GrupoInactivoException(GrupoException):
    """El grupo está inactivo o cancelado"""

    def __init__(self, codigo_grupo: str, estado_actual: str, razon: str = None):
        super().__init__(
            message=f"Grupo '{codigo_grupo}' está inactivo (estado: {estado_actual})",
            error_code="GRUPO_INACTIVO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_grupo": codigo_grupo,
                "estado_actual": estado_actual,
                "razon": razon,
            },
        )


class ConflictoHorarioException(GrupoException):
    """Conflicto de horarios entre grupos"""

    def __init__(
        self,
        grupo1: str,
        grupo2: str,
        dias_conflicto: list = None,
        horas_conflicto: str = None,
    ):
        super().__init__(
            message=f"Conflicto de horarios entre grupos '{grupo1}' y '{grupo2}'",
            error_code="CONFLICTO_HORARIO",
            http_status=status.HTTP_409_CONFLICT,
            details={
                "grupo1": grupo1,
                "grupo2": grupo2,
                "dias_conflicto": dias_conflicto or [],
                "horas_conflicto": horas_conflicto,
            },
        )


class PrerrequisitoNoCompletadoException(GrupoException):
    """El estudiante no cumple con los prerrequisitos para inscribirse al grupo"""

    def __init__(self, codigo_grupo: str, materia: str, prerrequisitos_faltantes: List[str]):
        super().__init__(
            message=f"No se puede inscribir al grupo '{codigo_grupo}' de la materia '{materia}'. Prerrequisitos faltantes: {', '.join(prerrequisitos_faltantes)}",
            error_code="PRERREQUISITO_NO_COMPLETADO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_grupo": codigo_grupo,
                "materia": materia,
                "prerrequisitos_faltantes": prerrequisitos_faltantes,
            },
        )


class InscripcionException(InscripcionBaseException):
    """Excepciones relacionadas con inscripciones"""
    pass


class InscripcionNoEncontradaException(InscripcionException):
    """La inscripción no existe"""

    def __init__(self, codigo_inscripcion: str):
        super().__init__(
            message=f"Inscripción '{codigo_inscripcion}' no encontrada",
            error_code="INSCRIPCION_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"codigo_inscripcion": codigo_inscripcion},
        )


class InscripcionDuplicadaException(InscripcionException):
    """El estudiante ya tiene una inscripción en el período"""

    def __init__(
        self,
        registro_academico: str,
        codigo_periodo: str,
        codigo_inscripcion_existente: str = None,
    ):
        super().__init__(
            message=f"Estudiante '{registro_academico}' ya está inscrito en el período '{codigo_periodo}'",
            error_code="INSCRIPCION_DUPLICADA",
            http_status=status.HTTP_409_CONFLICT,
            details={
                "registro_academico": registro_academico,
                "codigo_periodo": codigo_periodo,
                "inscripcion_existente": codigo_inscripcion_existente,
            },
        )


class GrupoDuplicadoException(InscripcionException):
    """El estudiante ya está inscrito en el grupo específico"""

    def __init__(self, registro_academico: str, codigo_grupo: str, codigo_periodo: str):
        super().__init__(
            message=f"Estudiante '{registro_academico}' ya está inscrito en el grupo '{codigo_grupo}' para el período '{codigo_periodo}'",
            error_code="GRUPO_DUPLICADO",
            http_status=status.HTTP_409_CONFLICT,
            details={
                "registro_academico": registro_academico,
                "codigo_grupo": codigo_grupo,
                "codigo_periodo": codigo_periodo,
            },
        )


class DetalleInscripcionNoEncontradoException(InscripcionException):
    """El detalle de inscripción (estudiante-grupo) no existe"""

    def __init__(self, codigo_inscripcion: str, codigo_grupo: str):
        super().__init__(
            message=f"No se encontró el detalle de inscripción para inscripción '{codigo_inscripcion}' y grupo '{codigo_grupo}'",
            error_code="DETALLE_INSCRIPCION_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={
                "codigo_inscripcion": codigo_inscripcion,
                "codigo_grupo": codigo_grupo
            }
        )


class InscripcionCanceladaException(InscripcionException):
    """La inscripción está cancelada"""

    def __init__(self, codigo_inscripcion: str, fecha_cancelacion: str = None, razon: str = None):
        super().__init__(
            message=f"La inscripción '{codigo_inscripcion}' está cancelada",
            error_code="INSCRIPCION_CANCELADA",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_inscripcion": codigo_inscripcion,
                "fecha_cancelacion": fecha_cancelacion,
                "razon_cancelacion": razon,
            },
        )


class LimiteMateriasExcedidoException(InscripcionException):
    """El estudiante excede el límite de materias por período"""

    def __init__(self, registro_academico: str, limite_maximo: int, materias_actuales: int):
        super().__init__(
            message=f"Estudiante '{registro_academico}' excede el límite de materias por período ({materias_actuales}/{limite_maximo})",
            error_code="LIMITE_MATERIAS_EXCEDIDO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "registro_academico": registro_academico,
                "limite_maximo": limite_maximo,
                "materias_actuales": materias_actuales,
            },
        )


class PlazoRetiroVencidoException(InscripcionException):
    """El plazo para retirarse de la materia ha vencido"""

    def __init__(self, codigo_grupo: str, fecha_limite: str = None):
        super().__init__(
            message=f"El plazo para retirarse del grupo '{codigo_grupo}' ha vencido",
            error_code="PLAZO_RETIRO_VENCIDO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "codigo_grupo": codigo_grupo,
                "fecha_limite_retiro": fecha_limite,
            },
        )


# ===== EXCEPCIONES TÉCNICAS =====


class DatabaseException(InscripcionBaseException):
    """Excepciones relacionadas con la base de datos"""

    def __init__(self, message: str, original_error: Exception = None, operation: str = None):
        super().__init__(
            message=f"Error de base de datos: {message}",
            error_code="DATABASE_ERROR",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "original_error": str(original_error) if original_error else None,
                "error_type": type(original_error).__name__ if original_error else None,
                "operation": operation,
            },
        )


class DatabaseConnectionException(DatabaseException):
    """Error de conexión a la base de datos"""

    def __init__(self, message: str = "Error de conexión a la base de datos"):
        super().__init__(
            message=message,
            error_code="DATABASE_CONNECTION_ERROR",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class DatabaseTimeoutException(DatabaseException):
    """Timeout en operación de base de datos"""

    def __init__(self, operation: str, timeout_seconds: float):
        super().__init__(
            message=f"Timeout en operación de base de datos: {operation}",
            error_code="DATABASE_TIMEOUT",
            http_status=status.HTTP_504_GATEWAY_TIMEOUT,
            details={
                "operation": operation,
                "timeout_seconds": timeout_seconds,
            },
        )


class TaskException(InscripcionBaseException):
    """Excepciones relacionadas con tareas asíncronas"""

    def __init__(self, task_id: str, message: str, original_error: Exception = None):
        super().__init__(
            message=f"Error en tarea '{task_id}': {message}",
            error_code="TASK_ERROR",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "task_id": task_id,
                "original_error": str(original_error) if original_error else None,
                "error_type": type(original_error).__name__ if original_error else None,
            },
        )


class TaskTimeoutException(TaskException):
    """Timeout en ejecución de tarea"""

    def __init__(self, task_id: str, timeout_seconds: float):
        super().__init__(
            task_id=task_id,
            message=f"La tarea excedió el tiempo límite de {timeout_seconds} segundos",
            error_code="TASK_TIMEOUT",
        )
        self.error_code = "TASK_TIMEOUT"


class TaskNotFoundException(TaskException):
    """Tarea no encontrada"""

    def __init__(self, task_id: str):
        super().__init__(
            task_id=task_id,
            message="Tarea no encontrada",
            error_code="TASK_NOT_FOUND",
        )
        self.error_code = "TASK_NOT_FOUND"
        self.http_status = status.HTTP_404_NOT_FOUND


class ValidationException(InscripcionBaseException):
    """Excepciones de validación de datos"""

    def __init__(self, field: str, value: Any, message: str):
        super().__init__(
            message=f"Error de validación en campo '{field}': {message}",
            error_code="VALIDATION_ERROR",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "field": field,
                "value": str(value),
                "validation_message": message,
            },
        )


class AuthenticationException(InscripcionBaseException):
    """Excepciones de autenticación"""

    def __init__(self, message: str = "Credenciales inválidas"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            http_status=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationException(InscripcionBaseException):
    """Excepciones de autorización"""

    def __init__(self, message: str = "Acceso denegado", required_permission: str = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            http_status=status.HTTP_403_FORBIDDEN,
            details={"required_permission": required_permission},
        )


class ConfigurationException(InscripcionBaseException):
    """Excepciones de configuración del sistema"""

    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            message=f"Error de configuración: {message}",
            error_code="CONFIGURATION_ERROR",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"config_key": config_key},
        )


class ExternalServiceException(InscripcionBaseException):
    """Excepciones relacionadas con servicios externos"""

    def __init__(self, service_name: str, message: str, status_code: int = None):
        super().__init__(
            message=f"Error en servicio externo '{service_name}': {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            http_status=status.HTTP_502_BAD_GATEWAY,
            details={
                "service_name": service_name,
                "external_status_code": status_code,
            },
        )


# ===== MAPEO DE ERRORES COMUNES =====


def map_common_exceptions(error: Exception) -> InscripcionBaseException:
    """
    Mapea excepciones comunes a excepciones personalizadas del sistema
    """
    if isinstance(error, ValueError):
        error_msg = str(error)

        # Mapear errores específicos basados en el mensaje
        if "no encontrado" in error_msg.lower():
            if "estudiante" in error_msg.lower():
                # Extraer registro académico del mensaje si es posible
                return EstudianteNoEncontradoException("UNKNOWN")
            elif "grupo" in error_msg.lower():
                return GrupoNoEncontradoException("UNKNOWN")
            elif "período" in error_msg.lower():
                return PeriodoNoEncontradoException("UNKNOWN")

        elif "no tiene cupo" in error_msg.lower():
            return GrupoSinCupoException("UNKNOWN", 0, 0)

        elif "conflicto de horarios" in error_msg.lower():
            return ConflictoHorarioException("UNKNOWN", "UNKNOWN")

        elif "ya está inscrito" in error_msg.lower():
            if "período" in error_msg.lower():
                return InscripcionDuplicadaException("UNKNOWN", "UNKNOWN")
            else:
                return GrupoDuplicadoException("UNKNOWN", "UNKNOWN", "UNKNOWN")

        elif "bloqueado" in error_msg.lower():
            return EstudianteBloqueadoException("UNKNOWN")

        # ValueError genérico
        return ValidationException("unknown", "unknown", error_msg)

    elif isinstance(error, KeyError):
        return ValidationException(str(error), "missing", "Campo requerido faltante")

    elif "database" in str(error).lower() or "postgresql" in str(error).lower():
        return DatabaseException(str(error), error)

    elif "timeout" in str(error).lower():
        if "database" in str(error).lower():
            return DatabaseTimeoutException("unknown", 0)
        else:
            return TaskTimeoutException("unknown", 0)

    elif "connection" in str(error).lower():
        return DatabaseConnectionException()

    else:
        # Error no mapeado - excepción genérica
        return InscripcionBaseException(
            message=f"Error interno del servidor: {str(error)}",
            error_code="INTERNAL_ERROR",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"original_error": str(error), "error_type": type(error).__name__},
        )


# ===== EXCEPCIONES DE HISTORIAL ACADÉMICO =====


class HistorialAcademicoException(InscripcionBaseException):
    """Clase base para excepciones relacionadas con historial académico"""
    pass


class MateriaNoEncontradaException(HistorialAcademicoException):
    """La materia especificada no existe"""

    def __init__(self, sigla_materia: str):
        super().__init__(
            message=f"Materia con sigla '{sigla_materia}' no encontrada",
            error_code="MATERIA_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"sigla_materia": sigla_materia},
        )


class HistorialNoEncontradoException(HistorialAcademicoException):
    """El registro de historial académico no existe"""

    def __init__(self, id_historial: str):
        super().__init__(
            message=f"Registro de historial con ID '{id_historial}' no encontrado",
            error_code="HISTORIAL_NOT_FOUND",
            http_status=status.HTTP_404_NOT_FOUND,
            details={"id_historial": id_historial},
        )


class HistorialDuplicadoException(HistorialAcademicoException):
    """Ya existe un registro de historial para la misma materia y período"""

    def __init__(
        self, registro_academico: str, sigla_materia: str, codigo_periodo: str
    ):
        super().__init__(
            message=f"Ya existe un registro para estudiante '{registro_academico}' en materia '{sigla_materia}' del período '{codigo_periodo}'",
            error_code="HISTORIAL_DUPLICADO",
            http_status=status.HTTP_409_CONFLICT,
            details={
                "registro_academico": registro_academico,
                "sigla_materia": sigla_materia,
                "codigo_periodo": codigo_periodo,
            },
        )


class EstadoMateriaInvalidoException(HistorialAcademicoException):
    """El estado de la materia no es válido"""

    def __init__(self, estado: str, estados_validos: List[str]):
        super().__init__(
            message=f"Estado '{estado}' no válido. Estados permitidos: {', '.join(estados_validos)}",
            error_code="ESTADO_MATERIA_INVALIDO",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "estado_proporcionado": estado,
                "estados_validos": estados_validos,
            },
        )


class NotaInvalidaException(HistorialAcademicoException):
    """La nota está fuera del rango válido"""

    def __init__(self, nota: float, min_nota: float = 0, max_nota: float = 100):
        super().__init__(
            message=f"Nota {nota} fuera del rango válido ({min_nota}-{max_nota})",
            error_code="NOTA_INVALIDA",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "nota_proporcionada": nota,
                "nota_minima": min_nota,
                "nota_maxima": max_nota,
            },
        )
