from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time
from decimal import Decimal

# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True

# Estudiante schemas
class EstudianteBase(BaseSchema):
    registro_academico: str
    codigo_carrera: str
    nombre: str
    apellido: str
    ci: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    estado_academico: str = "REGULAR"

class EstudianteResponse(EstudianteBase):
    pass

# Periodo Academico schemas
class PeriodoAcademicoBase(BaseSchema):
    codigo_periodo: str
    semestre: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[str] = None

class PeriodoAcademicoCreate(PeriodoAcademicoBase):
    pass

class PeriodoAcademicoUpdate(BaseSchema):
    semestre: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[str] = None

class PeriodoAcademicoResponse(PeriodoAcademicoBase):
    pass

# Materia schemas
class MateriaBase(BaseSchema):
    sigla: str
    nombre: str
    creditos: int
    es_electiva: bool = False

class MateriaResponse(MateriaBase):
    pass

# Docente schemas
class DocenteBase(BaseSchema):
    codigo_docente: str
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    ci: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None

class DocenteResponse(DocenteBase):
    pass

# Aula schemas
class AulaBase(BaseSchema):
    codigo_aula: str
    modulo: Optional[str] = None
    aula: Optional[str] = None
    capacidad: Optional[int] = None
    ubicacion: Optional[str] = None

class AulaResponse(AulaBase):
    pass

# Horario schemas
class HorarioBase(BaseSchema):
    codigo_horario: str
    dias_semana: List[str]
    hora_inicio: time
    hora_fin: time

class HorarioResponse(HorarioBase):
    pass

# Grupo schemas
class GrupoBase(BaseSchema):
    codigo_grupo: str
    sigla_materia: str
    codigo_docente: str
    codigo_aula: str
    codigo_horario: str
    descripcion: Optional[str] = None
    cupo: int = 40
    inscritos_actuales: int = 0

class GrupoSimpleResponse(GrupoBase):
    pass

class GrupoResponse(GrupoBase):
    materia: Optional[MateriaResponse] = None
    docente: Optional[DocenteResponse] = None
    aula: Optional[AulaResponse] = None
    horario: Optional[HorarioResponse] = None

# Inscripcion schemas
class InscripcionBase(BaseSchema):
    codigo_inscripcion: str
    registro_academico: str
    codigo_periodo: str
    fecha_inscripcion: date

class InscripcionCreate(BaseSchema):
    registro_academico: str
    codigo_periodo: str
    grupos: List[str] = Field(description="Lista de códigos de grupos a inscribir")

class InscripcionUpdate(BaseSchema):
    fecha_inscripcion: Optional[date] = None

# Respuesta simple sin relaciones para evitar problemas de lazy loading
class InscripcionSimpleResponse(BaseSchema):
    codigo_inscripcion: str
    registro_academico: str
    codigo_periodo: str
    fecha_inscripcion: date

# Respuesta completa con relaciones cargadas manualmente
class InscripcionResponse(InscripcionBase):
    estudiante: Optional[EstudianteResponse] = None
    periodo_academico: Optional[PeriodoAcademicoResponse] = None
    detalles: Optional[List["DetalleInscripcionSimpleResponse"]] = []

# Detalle Inscripcion schemas
class DetalleInscripcionBase(BaseSchema):
    codigo_detalle: str
    codigo_inscripcion: str
    codigo_grupo: str

class DetalleInscripcionCreate(BaseSchema):
    codigo_grupo: str

class DetalleInscripcionSimpleResponse(DetalleInscripcionBase):
    pass

class DetalleInscripcionResponse(DetalleInscripcionBase):
    grupo: Optional[GrupoSimpleResponse] = None

# Response schemas for complex queries
class InscripcionCompleteResponse(InscripcionResponse):
    total_creditos: int
    materias_inscritas: List[str]

# Request schemas for bulk operations
class BulkInscripcionRequest(BaseSchema):
    inscripciones: List[InscripcionCreate]

# Estadisticas schemas
class EstadisticasInscripcion(BaseSchema):
    total_inscripciones: int
    inscripciones_por_periodo: dict
    estudiantes_activos: int
    grupos_disponibles: int

# Historial Académico schemas
class HistorialAcademicoBase(BaseSchema):
    registro_academico: str = Field(..., description="Registro académico del estudiante")
    sigla_materia: str = Field(..., description="Sigla de la materia")
    codigo_periodo: str = Field(..., description="Código del período académico")
    nota_final: Optional[Decimal] = Field(None, ge=0, le=100, description="Nota final (0-100)")
    estado: str = Field(..., description="Estado de la materia")
    observacion: Optional[str] = Field(None, max_length=200, description="Observaciones adicionales")

class HistorialAcademicoCreate(HistorialAcademicoBase):
    pass

class HistorialAcademicoUpdate(BaseSchema):
    nota_final: Optional[Decimal] = Field(None, ge=0, le=100, description="Nota final (0-100)")
    estado: Optional[str] = Field(None, description="Estado de la materia")
    observacion: Optional[str] = Field(None, max_length=200, description="Observaciones adicionales")

class HistorialAcademicoResponse(HistorialAcademicoBase):
    id_historial: int
    fecha_registro: date
    
    # Información relacionada (opcional para respuestas detalladas)
    estudiante_nombre: Optional[str] = None
    materia_nombre: Optional[str] = None
    periodo_nombre: Optional[str] = None

class HistorialAcademicoCompleto(HistorialAcademicoResponse):
    # Incluye información completa de las relaciones
    estudiante: Optional['EstudianteBase'] = None
    materia: Optional['MateriaBase'] = None
    periodo: Optional['PeriodoAcademicoBase'] = None

# Esquemas para consultas especializadas
class ResumenAcademico(BaseSchema):
    registro_academico: str
    total_materias: int
    materias_aprobadas: int
    materias_reprobadas: int
    materias_retiradas: int
    promedio_general: Optional[Decimal] = None
    creditos_aprobados: int

class HistorialPorPeriodo(BaseSchema):
    codigo_periodo: str
    periodo_nombre: str
    materias: List[HistorialAcademicoResponse]
    promedio_periodo: Optional[Decimal] = None

# Error schemas
class ErrorResponse(BaseSchema):
    detail: str
    error_code: Optional[str] = None

# Update forward references
InscripcionResponse.model_rebuild()
HistorialAcademicoCompleto.model_rebuild()