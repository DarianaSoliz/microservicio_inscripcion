from sqlalchemy import Column, String, Integer, Date, ForeignKey, DateTime, Boolean, ARRAY, Time, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import date, datetime

class Carrera(Base):
    __tablename__ = "carrera"
    
    codigo_carrera = Column(String(8), primary_key=True)
    nombre = Column(String(100), nullable=False)
    
    # Relationships
    estudiantes = relationship("Estudiante", back_populates="carrera")

class PlanEstudio(Base):
    __tablename__ = "plan_estudio"
    
    codigo_plan = Column(String(8), primary_key=True)
    plan = Column(String(10))
    cant_semestre = Column(Integer, nullable=False)
    codigo_carrera = Column(String(8), ForeignKey("carrera.codigo_carrera"))

class Materia(Base):
    __tablename__ = "materia"
    
    sigla = Column(String(8), primary_key=True)
    nombre = Column(String(100), nullable=False)
    creditos = Column(Integer, nullable=False)
    es_electiva = Column(Boolean, default=False)
    
    # Relationships
    grupos = relationship("Grupo", back_populates="materia")
    historial_academico = relationship("HistorialAcademico", back_populates="materia")

class Docente(Base):
    __tablename__ = "docente"
    
    codigo_docente = Column(String(8), primary_key=True)
    nombre = Column(String(50))
    apellido = Column(String(50))
    ci = Column(String(20))
    correo = Column(String(100))
    telefono = Column(String(20))
    
    # Relationships
    grupos = relationship("Grupo", back_populates="docente")

class Aula(Base):
    __tablename__ = "aula"
    
    codigo_aula = Column(String(8), primary_key=True)
    modulo = Column(String(10))
    aula = Column(String(10))
    capacidad = Column(Integer)
    ubicacion = Column(String(100))
    
    # Relationships
    grupos = relationship("Grupo", back_populates="aula")

class Horario(Base):
    __tablename__ = "horario"
    
    codigo_horario = Column(String(8), primary_key=True)
    dias_semana = Column(ARRAY(String), nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    
    # Relationships
    grupos = relationship("Grupo", back_populates="horario")

class Grupo(Base):
    __tablename__ = "grupo"
    
    codigo_grupo = Column(String(8), primary_key=True)
    sigla_materia = Column(String(8), ForeignKey("materia.sigla"))
    codigo_docente = Column(String(8), ForeignKey("docente.codigo_docente"))
    codigo_aula = Column(String(8), ForeignKey("aula.codigo_aula"))
    codigo_horario = Column(String(8), ForeignKey("horario.codigo_horario"))
    descripcion = Column(String(150))
    cupo = Column(Integer, default=40)
    inscritos_actuales = Column(Integer, default=0)
    
    # Relationships
    materia = relationship("Materia", back_populates="grupos")
    docente = relationship("Docente", back_populates="grupos")
    aula = relationship("Aula", back_populates="grupos")
    horario = relationship("Horario", back_populates="grupos")
    detalles_inscripcion = relationship("DetalleInscripcion", back_populates="grupo")

class Estudiante(Base):
    __tablename__ = "estudiante"
    
    registro_academico = Column(String(10), primary_key=True)
    codigo_carrera = Column(String(8), ForeignKey("carrera.codigo_carrera"))
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    ci = Column(String(20), unique=True)
    correo = Column(String(100))
    contrasena = Column(Text, nullable=False)
    telefono = Column(String(20))
    direccion = Column(String(150))
    estado_academico = Column(String(20), default='REGULAR')
    
    # Relationships
    carrera = relationship("Carrera", back_populates="estudiantes")
    inscripciones = relationship("Inscripcion", back_populates="estudiante")
    pagos = relationship("Pago", back_populates="estudiante")
    bloqueos = relationship("Bloqueo", back_populates="estudiante")
    historial_academico = relationship("HistorialAcademico", back_populates="estudiante")

class PeriodoAcademico(Base):
    __tablename__ = "periodo_academico"
    
    codigo_periodo = Column(String(8), primary_key=True)
    semestre = Column(String(10))
    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    estado = Column(String(15))
    
    # Relationships
    inscripciones = relationship("Inscripcion", back_populates="periodo_academico")
    historial_academico = relationship("HistorialAcademico", back_populates="periodo")

class Inscripcion(Base):
    __tablename__ = "inscripcion"
    
    codigo_inscripcion = Column(String(10), primary_key=True)
    registro_academico = Column(String(10), ForeignKey("estudiante.registro_academico"))
    codigo_periodo = Column(String(8), ForeignKey("periodo_academico.codigo_periodo"))
    fecha_inscripcion = Column(Date, default=func.current_date())
    
    # Relationships
    estudiante = relationship("Estudiante", back_populates="inscripciones")
    periodo_academico = relationship("PeriodoAcademico", back_populates="inscripciones")
    detalles = relationship("DetalleInscripcion", back_populates="inscripcion")

class DetalleInscripcion(Base):
    __tablename__ = "detalle_inscripcion"
    
    codigo_detalle = Column(String(10), primary_key=True)
    codigo_inscripcion = Column(String(10), ForeignKey("inscripcion.codigo_inscripcion"))
    codigo_grupo = Column(String(8), ForeignKey("grupo.codigo_grupo"))
    
    # Relationships
    inscripcion = relationship("Inscripcion", back_populates="detalles")
    grupo = relationship("Grupo", back_populates="detalles_inscripcion")

class Pago(Base):
    __tablename__ = "pago"
    
    codigo_pago = Column(String(10), primary_key=True)
    registro_academico = Column(String(10), ForeignKey("estudiante.registro_academico"))
    descripcion = Column(String(100))
    monto = Column(Numeric(10, 2))
    fecha_pago = Column(Date, default=func.current_date())
    
    # Relationships
    estudiante = relationship("Estudiante", back_populates="pagos")

class Bloqueo(Base):
    __tablename__ = "bloqueo"
    
    codigo_bloqueo = Column(String(10), primary_key=True)
    registro_academico = Column(String(10), ForeignKey("estudiante.registro_academico"))
    descripcion = Column(String(100))
    
    # Relationships
    estudiante = relationship("Estudiante", back_populates="bloqueos")

class HistorialAcademico(Base):
    __tablename__ = "historial_academico"
    
    id_historial = Column(Integer, primary_key=True, autoincrement=True)
    registro_academico = Column(String(10), ForeignKey("estudiante.registro_academico"), nullable=False)
    sigla_materia = Column(String(8), ForeignKey("materia.sigla"), nullable=False)
    codigo_periodo = Column(String(8), ForeignKey("periodo_academico.codigo_periodo"), nullable=False)
    nota_final = Column(Numeric(5,2), nullable=True)
    estado = Column(String(15), nullable=False)
    observacion = Column(String(200), nullable=True)
    fecha_registro = Column(Date, default=func.current_date())
    
    # Relationships
    estudiante = relationship("Estudiante", back_populates="historial_academico")
    materia = relationship("Materia", back_populates="historial_academico")
    periodo = relationship("PeriodoAcademico", back_populates="historial_academico")
    
    # Constraints
    __table_args__ = (
        # Constraint para nota_final entre 0 y 100
        # Se manejará en la validación de la aplicación
        # Constraint para estado
        # Se manejará en la validación de la aplicación
    )