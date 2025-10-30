from celery import Celery
from kombu import Queue
from app.core.config import settings

# Crear instancia de Celery
celery_app = Celery(
    "inscription_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

# Configuración de Celery con tolerancia a fallos mejorada
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Configuración de colas con DLQ (Dead Letter Queue)
    task_routes={
        "app.tasks.create_inscription_task": {"queue": "inscripciones"},
        "app.tasks.bulk_create_inscriptions_task": {"queue": "inscripciones_bulk"},
        "app.tasks.create_single_group_inscription_task": {"queue": "inscripciones_individual"},
        "app.tasks.health_check_task": {"queue": "health_check"},
    },
    
    # Configuración de colas detallada
    task_queues=(
        Queue('inscripciones', routing_key='inscripciones'),
        Queue('inscripciones_bulk', routing_key='inscripciones_bulk'),
        Queue('inscripciones_individual', routing_key='inscripciones_individual'),
        Queue('health_check', routing_key='health_check'),
        Queue('inscripciones_dlq', routing_key='inscripciones_dlq'),  # Dead Letter Queue
    ),
    
    # Configuración de workers
    worker_prefetch_multiplier=1,  # Previene acumulación de tareas
    task_acks_late=True,           # Confirma solo después de completar
    worker_max_tasks_per_child=100, # Recicla workers para prevenir memory leaks
    worker_disable_rate_limits=False,
    
    # Configuración de resultados
    result_expires=3600,  # 1 hora
    task_track_started=True,
    task_ignore_result=False,
    result_persistent=True,  # Persiste resultados en Redis
    
    # Configuración de retry con backoff exponencial
    task_default_retry_delay=10,    # Delay inicial de 10 segundos
    task_max_retries=5,             # Máximo 5 reintentos
    task_retry_backoff=2,           # Factor de backoff exponencial
    task_retry_backoff_max=300,     # Máximo 5 minutos entre reintentos
    task_retry_jitter=True,         # Agrega jitter para evitar thundering herd
    
    # Configuración de timeouts
    task_soft_time_limit=300,       # 5 minutos soft limit
    task_time_limit=600,            # 10 minutos hard limit
    
    # Configuración de broker para tolerancia a fallos
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Configuración de serialización segura
    task_compression='gzip',
    result_compression='gzip',
    
    # Configuración de monitoreo
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Configuración de pool
    worker_pool='threads',          # Usa threads para operaciones I/O bound
    worker_concurrency=4,           # 4 threads por worker
)

# Configuración de colas
celery_app.conf.task_default_queue = settings.DEFAULT_QUEUE_NAME

# Configuración de handlers de señales para logging y monitoreo
@celery_app.task(bind=True)
def retry_task_with_backoff(self, func, *args, **kwargs):
    """
    Wrapper para tareas con retry y backoff exponencial personalizado
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        # Calcular delay con backoff exponencial
        delay = min(
            celery_app.conf.task_default_retry_delay * (celery_app.conf.task_retry_backoff ** self.request.retries),
            celery_app.conf.task_retry_backoff_max
        )
        
        # Retry solo en ciertos tipos de excepciones
        retryable_exceptions = (
            ConnectionError,
            TimeoutError,
            OSError,
            # Agregar más excepciones según necesidad
        )
        
        if isinstance(exc, retryable_exceptions):
            raise self.retry(exc=exc, countdown=delay, max_retries=celery_app.conf.task_max_retries)
        else:
            # No hacer retry en errores de lógica de negocio
            raise exc