# Sistema de Logging y Excepciones - Microservicio de Registro Académico

## 📋 Descripción

Este microservicio implementa un sistema avanzado de logging y manejo de excepciones para la gestión de inscripciones y registro académico. El sistema proporciona trazabilidad completa, manejo robusto de errores y capacidades de monitoreo.

## 🚀 Características

### Sistema de Logging

- **Logging con colores**: Formateo visual para diferentes niveles de log
- **Rotación automática**: Archivos de log con rotación por tamaño
- **Múltiples handlers**: Consola, archivos específicos por funcionalidad
- **Contexto enriquecido**: Request IDs, información de usuario, métricas de tiempo
- **Decoradores**: Para logging automático de funciones y operaciones

### Manejo de Excepciones

- **Excepciones específicas**: Para cada dominio del negocio
- **Mapeo automático**: De excepciones comunes a excepciones personalizadas
- **Responses estandarizados**: Formato consistente de errores
- **Logging automático**: Todas las excepciones se loggean automáticamente

### Middleware

- **Logging de requests**: Información completa de cada request/response
- **Seguridad**: Detección de patrones sospechosos
- **Base de datos**: Logging específico para operaciones de BD
- **Métricas**: Tiempo de procesamiento, IPs, user agents

## 🔧 Configuración

### Variables de Entorno

```bash
# Configuración de logging
LOG_LEVEL="INFO"      # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR="logs"        # Directorio donde guardar los logs
LOG_CONSOLE="true"    # Mostrar logs en consola (true/false)
LOG_FILE="true"       # Guardar logs en archivos (true/false)
```

### Archivos de Log

El sistema genera los siguientes archivos de log:

```
logs/
├── app.log          # Log general de la aplicación
├── errors.log       # Solo errores y críticos
├── requests.log     # Requests HTTP con formato especial
├── database.log     # Operaciones de base de datos
└── tasks.log        # Tareas de Celery
```

## 📖 Uso

### 1. Logging en Servicios

```python
from app.core.logging import get_logger, log_service_operation, log_execution_time

logger = get_logger(__name__)

@log_service_operation("historial")
@log_execution_time
async def create_historial(self, data):
    logger.info(
        "Creando registro de historial",
        extra={
            "registro_academico": data.registro_academico,
            "materia": data.sigla_materia
        }
    )
    # ... lógica del servicio
```

### 2. Logging en Routers

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

@router.post("/historial")
async def create_historial(data, request: Request):
    logger.info(
        "Endpoint de creación de historial llamado",
        extra={
            "request_id": getattr(request.state, 'request_id', None),
            "data": data.dict()
        }
    )
    # ... lógica del endpoint
```

### 3. Excepciones Personalizadas

```python
from app.exceptions import (
    EstudianteNoEncontradoException,
    EstadoMateriaInvalidoException,
    DatabaseException
)

# Excepciones específicas del dominio
raise EstudianteNoEncontradoException("EST001")

# Excepciones con detalles
raise EstadoMateriaInvalidoException("INVALIDO", ["APROBADA", "REPROBADA"])

# Excepciones técnicas
try:
    # operación de BD
    pass
except Exception as e:
    raise DatabaseException("Error en consulta", e, "READ")
```

### 4. Decoradores de Logging

```python
from app.core.logging import log_function_call, log_execution_time, log_database_operation

# Para logging automático de llamadas
@log_function_call
def calculate_average(grades):
    return sum(grades) / len(grades)

# Para medir tiempo de ejecución
@log_execution_time
async def complex_operation():
    # operación compleja
    pass

# Para operaciones de BD
@log_database_operation("CREATE")
async def create_record(db, data):
    # crear registro
    pass
```

## 🏗️ Estructura del Sistema

### Excepciones por Dominio

#### Estudiantes
- `EstudianteNoEncontradoException`
- `EstudianteBloqueadoException`
- `EstudianteInactivoException`
- `EstudianteSuspendidoException`

#### Períodos Académicos
- `PeriodoNoEncontradoException`
- `PeriodoInactivoException`
- `PeriodoInscripcionCerradoException`
- `PeriodoInscripcionNoIniciadoException`

#### Grupos
- `GrupoNoEncontradoException`
- `GrupoSinCupoException`
- `GrupoInactivoException`
- `ConflictoHorarioException`
- `PrerrequisitoNoCompletadoException`

#### Inscripciones
- `InscripcionNoEncontradaException`
- `InscripcionDuplicadaException`
- `InscripcionCanceladaException`
- `LimiteMateriasExcedidoException`
- `PlazoRetiroVencidoException`

#### Historial Académico
- `HistorialNoEncontradoException`
- `HistorialDuplicadoException`
- `EstadoMateriaInvalidoException`
- `NotaInvalidaException`

#### Técnicas
- `DatabaseException`
- `DatabaseConnectionException`
- `DatabaseTimeoutException`
- `TaskException`
- `ValidationException`
- `AuthenticationException`
- `AuthorizationException`

### Middleware Stack

1. **LoggingMiddleware**: Logging de requests/responses
2. **SecurityLoggingMiddleware**: Detección de amenazas
3. **DatabaseLoggingMiddleware**: Logging de operaciones BD
4. **CORSMiddleware**: Configuración de CORS

## 📊 Monitoreo de Logs

### 🖥️ **Monitoreo Local (Recomendado)**

Los logs se escriben tanto en el contenedor como en tu directorio local `./logs/` gracias al volumen montado en `docker-compose.yml`.

#### **PowerShell (Windows):**
```powershell
# Log general de la aplicación
Get-Content -Path .\logs\app.log -Wait -Tail 10

# Solo errores críticos
Get-Content -Path .\logs\errors.log -Wait -Tail 10

# Requests HTTP con trazabilidad
Get-Content -Path .\logs\requests.log -Wait -Tail 10

# Operaciones de base de datos
Get-Content -Path .\logs\database.log -Wait -Tail 10

# Logs de tareas Celery
Get-Content -Path .\logs\tasks.log -Wait -Tail 10

# Múltiples archivos simultáneamente
Get-Content -Path .\logs\app.log, .\logs\errors.log -Wait -Tail 10
```

#### **Git Bash / WSL / Linux:**
```bash
# Log general de la aplicación
tail -f logs/app.log

# Solo errores críticos
tail -f logs/errors.log

# Requests HTTP con trazabilidad
tail -f logs/requests.log

# Operaciones de base de datos
tail -f logs/database.log

# Logs de tareas Celery
tail -f logs/tasks.log

# Múltiples archivos simultáneamente
tail -f logs/app.log logs/errors.log logs/requests.log
```

### 🐳 **Monitoreo de Contenedores Docker**

Para logs que solo van a stdout/stderr del proceso:

```bash
# Todos los logs del contenedor principal
docker-compose logs -f inscription-microservice

# Logs de workers Celery
docker-compose logs -f celery-worker-1
docker-compose logs -f celery-worker-2
docker-compose logs -f celery-worker-bulk

# Logs de Flower (monitor Celery)
docker-compose logs -f flower

# Todos los servicios
docker-compose logs -f

# Ver logs con timestamps
docker-compose logs -t inscription-microservice

# Solo últimas 50 líneas
docker-compose logs --tail=50 inscription-microservice
```

### 🔍 **Análisis y Filtrado de Logs**

#### **PowerShell:**
```powershell
# Buscar errores específicos
Select-String -Path .\logs\app.log -Pattern "ERROR"

# Ver últimas 100 líneas
Get-Content -Path .\logs\app.log -Tail 100

# Filtrar por fecha específica
Select-String -Path .\logs\app.log -Pattern "2025-10-28"

# Contar errores
(Select-String -Path .\logs\errors.log -Pattern "ERROR").Count

# Buscar requests de un endpoint específico
Select-String -Path .\logs\requests.log -Pattern "/inscripciones"

# Filtrar por nivel de log específico
Select-String -Path .\logs\app.log -Pattern "WARNING|ERROR|CRITICAL"

# Buscar por Request ID específico
Select-String -Path .\logs\app.log -Pattern "\[abc12345\]"

# Ver logs en tiempo real con filtro
Get-Content -Path .\logs\app.log -Wait | Where-Object { $_ -match "ERROR" }
```

#### **Bash/Linux:**
```bash
# Buscar errores específicos
grep "ERROR" logs/app.log

# Ver últimas 100 líneas
tail -n 100 logs/app.log

# Filtrar por fecha específica
grep "2025-10-28" logs/app.log

# Contar requests por minuto
grep "$(date '+%Y-%m-%d %H:%M')" logs/requests.log | wc -l

# Buscar requests de un endpoint específico
grep "/inscripciones" logs/requests.log

# Errores en tiempo real con colores
tail -f logs/errors.log | grep --color=always "ERROR"

# Buscar por Request ID específico
grep "\[abc12345\]" logs/app.log

# Ver solo warnings y errores
tail -f logs/app.log | grep -E "(WARNING|ERROR|CRITICAL)"

# Análisis de performance (requests más lentos)
grep "X-Process-Time" logs/app.log | sort -k4 -nr | head -10

# Contar errores por tipo
grep "ERROR" logs/app.log | cut -d'-' -f6 | sort | uniq -c
```

### 📈 **Herramientas Avanzadas de Monitoreo**

#### **Multitail (para múltiples archivos):**
```bash
# Instalar multitail (Git Bash con chocolatey o WSL)
choco install multitail  # Windows
apt-get install multitail # Ubuntu/WSL

# Ver múltiples logs en ventanas separadas
multitail logs/app.log logs/errors.log logs/requests.log
```

#### **Log Analysis (lnav):**
```bash
# Instalar lnav para análisis avanzado
# Windows: usar WSL o descargar binario
# Ver todos los logs con análisis automático
lnav logs/
```

#### **Monitoring en tiempo real:**
```bash
# Ver estadísticas en tiempo real
watch -n 1 'wc -l logs/*.log'

# Monitor de errores
watch -n 5 'tail -n 20 logs/errors.log'

# Conteo de requests por minuto
watch -n 60 'grep "$(date "+%Y-%m-%d %H:%M")" logs/requests.log | wc -l'
```

## 📊 Monitoreo

### Request ID

Cada request recibe un ID único que se propaga por todo el sistema:

```python
request_id = request.state.request_id  # Disponible en todos los handlers
```

### Headers de Response

```
X-Request-ID: abc12345
X-Process-Time: 0.1234
```

### Formato de Logs

```
2024-10-28 10:30:45 - app.routers.historial - INFO - historial.py:45 - [abc12345] [User:EST001] - Creando registro de historial
```

## 🔍 Ejemplos de Logs

### Request Log
```
2024-10-28 10:30:45 - app.middleware.logging - INFO - Request iniciado: POST /api/v1/historial
```

### Service Log
```
2024-10-28 10:30:45 - app.services.historial - INFO - Servicio historial.create_historial completado exitosamente
```

### Error Log
```
2024-10-28 10:30:45 - app.services.historial - ERROR - Error en servicio historial.create_historial: Estudiante no encontrado
```

### Security Log
```
2024-10-28 10:30:45 - app.security - WARNING - Suspicious pattern detected: script
```

## 🛠️ Personalización

### Agregar Nuevo Logger

```python
# 1. En logging.py, agregar configuración
'app.mi_modulo': {
    'level': log_level,
    'handlers': [],
    'propagate': True
}

# 2. En tu módulo
from app.core.logging import get_logger
logger = get_logger(__name__)
```

### Agregar Nueva Excepción

```python
# En exceptions.py
class MiNuevaException(InscripcionBaseException):
    def __init__(self, parametro: str):
        super().__init__(
            message=f"Error personalizado: {parametro}",
            error_code="MI_ERROR",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"parametro": parametro}
        )
```

### Nuevo Decorador de Logging

```python
def log_custom_operation(operation_name: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger('app.custom')
            logger.info(f"Operación {operation_name} iniciada")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Operación {operation_name} completada")
                return result
            except Exception as e:
                logger.error(f"Error en operación {operation_name}: {e}")
                raise
        return wrapper
    return decorator
```

## 🚀 Deployment

### Variables de Producción

```bash
LOG_LEVEL="WARNING"
LOG_CONSOLE="false"
LOG_FILE="true"
LOG_DIR="/app/logs"
```

### Docker Compose

```yaml
services:
  app:
    volumes:
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=INFO
      - LOG_DIR=/app/logs
```

## 📝 Mejores Prácticas

1. **Niveles de Log**:
   - `DEBUG`: Información de desarrollo
   - `INFO`: Flujo normal de la aplicación
   - `WARNING`: Situaciones que requieren atención
   - `ERROR`: Errores que no impiden el funcionamiento
   - `CRITICAL`: Errores que pueden detener la aplicación

2. **Información Sensible**:
   - Nunca loggear contraseñas o tokens
   - Usar máscaras para datos sensibles
   - Considerar regulaciones de privacidad

3. **Performance**:
   - Usar logging asíncrono para alta carga
   - Configurar rotación apropiada
   - Monitorear el uso de disco

4. **Contexto**:
   - Incluir siempre request_id
   - Agregar información relevante en extra
   - Usar formatos consistentes

## 🐛 Troubleshooting

### Logs no Aparecen
- Verificar `LOG_LEVEL`
- Verificar permisos del directorio `LOG_DIR`
- Revisar configuración de handlers

### Performance Lento
- Reducir nivel de logging
- Configurar handlers asíncronos
- Optimizar rotación de archivos

### Archivos de Log Grandes
- Configurar `maxBytes` más pequeño
- Aumentar `backupCount`
- Implementar limpieza automática

## � Comandos Rápidos de Monitoreo

### **Inicio Rápido - PowerShell:**
```powershell
# Ver actividad general
Get-Content -Path .\logs\app.log -Wait -Tail 20

# Solo errores en tiempo real
Get-Content -Path .\logs\errors.log -Wait -Tail 10

# Todos los logs importantes
Get-Content -Path .\logs\app.log, .\logs\errors.log, .\logs\requests.log -Wait -Tail 5
```

### **Inicio Rápido - Bash/Linux:**
```bash
# Ver actividad general
tail -f logs/app.log

# Solo errores en tiempo real
tail -f logs/errors.log

# Todos los logs importantes
tail -f logs/app.log logs/errors.log logs/requests.log
```

### **Debug de Problemas Específicos:**
```powershell
# Buscar errores de las últimas 2 horas
$desde = (Get-Date).AddHours(-2).ToString("yyyy-MM-dd HH:")
Select-String -Path .\logs\app.log -Pattern $desde | Select-String "ERROR"

# Requests fallidos (status 4xx, 5xx)
Select-String -Path .\logs\requests.log -Pattern "(40[0-9]|50[0-9])"

# Problemas de base de datos
Select-String -Path .\logs\database.log -Pattern "(timeout|connection|deadlock)"
```

## 🛠️ Configuración del Volumen

El monitoreo local funciona gracias a esta configuración en `docker-compose.yml`:

```yaml
services:
  inscription-microservice:
    volumes:
      - ./logs:/app/logs  # ← Esta línea monta los logs localmente
```

### **Verificar que el volumen está funcionando:**
```powershell
# Verificar que los archivos existen localmente
Get-ChildItem -Path "logs"

# Verificar que se están escribiendo
Get-Content -Path .\logs\app.log -Tail 5
```

## �📚 Referencias

- [Python Logging](https://docs.python.org/3/library/logging.html)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [Structured Logging](https://structlog.readthedocs.io/)