"""
Configuración centralizada de logging para el microservicio de registro académico.
"""

import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class ColoredFormatter(logging.Formatter):
    """Formatter personalizado con colores para la consola."""
    
    # Códigos de color ANSI
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Verde
        'WARNING': '\033[33m',    # Amarillo
        'ERROR': '\033[31m',      # Rojo
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Aplicar color basado en el nivel
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Formatear el mensaje original
        message = super().format(record)
        
        # Aplicar color solo al nivel de log
        colored_level = f"{color}{record.levelname}{reset}"
        message = message.replace(record.levelname, colored_level, 1)
        
        return message


class RequestFormatter(logging.Formatter):
    """Formatter personalizado para requests HTTP."""
    
    def format(self, record):
        # Agregar información adicional si está disponible
        if hasattr(record, 'request_id'):
            record.request_id = f"[{record.request_id}]"
        else:
            record.request_id = ""
            
        if hasattr(record, 'user_id'):
            record.user_id = f"[User:{record.user_id}]"
        else:
            record.user_id = ""
            
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    console_output: bool = True,
    file_output: bool = True
) -> None:
    """
    Configura el sistema de logging.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio donde guardar los logs
        console_output: Si mostrar logs en consola
        file_output: Si guardar logs en archivo
    """
    
    # Crear directorio de logs si no existe
    if file_output:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
    
    # Configuración base
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '%(asctime)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'colored': {
                '()': ColoredFormatter,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'request': {
                '()': RequestFormatter,
                'format': '%(asctime)s %(request_id)s %(user_id)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {},
        'loggers': {
            '': {  # Root logger
                'level': log_level,
                'handlers': []
            },
            'app': {
                'level': log_level,
                'handlers': [],
                'propagate': False
            },
            'app.routers': {
                'level': log_level,
                'handlers': [],
                'propagate': True
            },
            'app.services': {
                'level': log_level,
                'handlers': [],
                'propagate': True
            },
            'app.core.database': {
                'level': log_level,
                'handlers': [],
                'propagate': True
            },
            'app.tasks': {
                'level': log_level,
                'handlers': [],
                'propagate': True
            },
            'app.middleware': {
                'level': log_level,
                'handlers': [],
                'propagate': True
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': [],
                'propagate': False
            },
            'sqlalchemy.engine': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True
            },
            'celery': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True
            }
        }
    }
    
    # Handler para consola
    if console_output:
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'colored',
            'stream': sys.stdout
        }
        # Agregar handler de consola a todos los loggers
        for logger_name in config['loggers']:
            config['loggers'][logger_name]['handlers'].append('console')
    
    # Handlers para archivos
    if file_output:
        # Log general de la aplicación
        config['handlers']['file_app'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'app.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8'
        }
        
        # Log de errores
        config['handlers']['file_error'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'errors.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 10,
            'encoding': 'utf-8'
        }
        
        # Log de requests HTTP
        config['handlers']['file_requests'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'request',
            'filename': os.path.join(log_dir, 'requests.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8'
        }
        
        # Log de base de datos
        config['handlers']['file_database'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'database.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5MB
            'backupCount': 3,
            'encoding': 'utf-8'
        }
        
        # Log de tareas Celery
        config['handlers']['file_tasks'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': os.path.join(log_dir, 'tasks.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5MB
            'backupCount': 3,
            'encoding': 'utf-8'
        }
        
        # Agregar handlers de archivo a los loggers correspondientes
        config['loggers']['']['handlers'].extend(['file_app', 'file_error'])
        config['loggers']['app']['handlers'].extend(['file_app', 'file_error'])
        config['loggers']['app.core.database']['handlers'].append('file_database')
        config['loggers']['app.tasks']['handlers'].append('file_tasks')
        config['loggers']['celery']['handlers'].append('file_tasks')
        config['loggers']['uvicorn.access']['handlers'].append('file_requests')
    
    # Aplicar configuración
    logging.config.dictConfig(config)
    
    # Log inicial
    logger = logging.getLogger('app.config.logging')
    logger.info(f"Sistema de logging configurado - Nivel: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger con el nombre especificado.
    
    Args:
        name: Nombre del logger (generalmente __name__)
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


def log_function_call(func):
    """
    Decorador para loggear llamadas a funciones.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada
    """
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Llamando a {func.__name__} con args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completado exitosamente")
            return result
        except Exception as e:
            logger.error(f"Error en {func.__name__}: {str(e)}", exc_info=True)
            raise
    
    return wrapper


def log_execution_time(func):
    """
    Decorador para loggear tiempo de ejecución de funciones.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada
    """
    def wrapper(*args, **kwargs):
        import time
        logger = get_logger(func.__module__)
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} ejecutado en {execution_time:.4f} segundos")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} falló después de {execution_time:.4f} segundos: {str(e)}")
            raise
    
    return wrapper


def log_database_operation(operation_type: str):
    """
    Decorador específico para operaciones de base de datos.
    
    Args:
        operation_type: Tipo de operación (CREATE, READ, UPDATE, DELETE)
        
    Returns:
        Decorador
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger('app.core.database')
            logger.info(f"Iniciando operación {operation_type} - {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Operación {operation_type} completada exitosamente - {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error en operación {operation_type} - {func.__name__}: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator


def log_service_operation(service_name: str):
    """
    Decorador específico para operaciones de servicios.
    
    Args:
        service_name: Nombre del servicio
        
    Returns:
        Decorador
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(f'app.services.{service_name}')
            logger.info(f"Ejecutando {func.__name__} en servicio {service_name}")
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Servicio {service_name}.{func.__name__} completado exitosamente")
                return result
            except Exception as e:
                logger.error(f"Error en servicio {service_name}.{func.__name__}: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator


# Helper to configure uvicorn loggers to use our formatter/level so they appear in the same stream
def configure_uvicorn_logging():
    """Configura los loggers de uvicorn para usar nuestro formato."""
    uvicorn_loggers = ('uvicorn', 'uvicorn.access', 'uvicorn.error')
    for name in uvicorn_loggers:
        uv_logger = logging.getLogger(name)
        # Remove existing handlers and attach a StreamHandler to stdout
        if uv_logger.handlers:
            uv_logger.handlers.clear()
        handler = logging.StreamHandler(stream=sys.stdout)
        fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handler.setFormatter(logging.Formatter(fmt))
        level = os.getenv('LOG_LEVEL', 'INFO').upper()
        uv_logger.setLevel(logging.getLevelName(level))
        uv_logger.addHandler(handler)
        uv_logger.propagate = False


# Configurar logging al importar el módulo
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
log_dir = os.getenv('LOG_DIR', 'logs')
console_output = os.getenv('LOG_CONSOLE', 'true').lower() == 'true'
file_output = os.getenv('LOG_FILE', 'true').lower() == 'true'

setup_logging(
    log_level=log_level,
    log_dir=log_dir,
    console_output=console_output,
    file_output=file_output
)
