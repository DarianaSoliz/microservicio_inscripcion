# 🎯 GUÍA DE ACCESO A TODOS LOS COMPONENTES

## 🚀 Iniciar todo el sistema

```bash
# Hacer scripts ejecutables
chmod +x *.sh

# Iniciar Redis + Workers + Flower
./start_all.sh

# En otra terminal, iniciar API principal
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## 📊 URLs de acceso

| Componente | URL | Descripción |
|------------|-----|-------------|
| **API Principal** | `http://0.0.0.0:8003` | Microservicio FastAPI |
| **Documentación** | `http://0.0.0.0:8003/docs` | Swagger UI |
| **Health Check** | `http://0.0.0.0:8003/health` | Estado del sistema |
| **Flower** | `http://0.0.0.0:5555` | Monitor de Celery |
| **Redis** | `localhost:6379` | Base de datos Redis |

## 🐝 Workers de Celery

### Worker 1
```bash
# Iniciar manualmente
./start_worker1.sh

# Ver logs
tail -f logs/worker1.log

# Colas: inscripciones, default
```

### Worker 2
```bash
# Iniciar manualmente  
./start_worker2.sh

# Ver logs
tail -f logs/worker2.log

# Colas: inscripciones, bulk_inscriptions
```

## 🌸 Flower (Monitor de Celery)

```bash
# Iniciar manualmente
./start_flower.sh

# Acceder
http://0.0.0.0:5555

# Credenciales (si se configuró autenticación)
Usuario: admin
Contraseña: password
```

## 🔴 Redis

```bash
# Iniciar Redis
sudo systemctl start redis

# Monitorear Redis
./monitor_redis.sh

# Acceso directo
redis-cli

# Ver colas de Celery
redis-cli keys "celery*"
```

## 📝 Monitoreo y comandos útiles

### Ver estado de Workers
```bash
celery -A app.core.celery_app inspect active
celery -A app.core.celery_app inspect stats
celery -A app.core.celery_app inspect active_queues
```

### Ver logs en tiempo real
```bash
tail -f logs/worker1.log
tail -f logs/worker2.log  
tail -f logs/flower.log
```

### Enviar tarea de prueba
```bash
# Desde Python
python3 -c "
from app.tasks import process_inscription_async
result = process_inscription_async.delay({'test': 'data'})
print(f'Task ID: {result.id}')
"
```

## 🛑 Parar el sistema

```bash
# Parar Workers + Flower
./stop_all.sh

# Parar API (Ctrl+C en la terminal donde corre)

# Parar Redis (opcional)
sudo systemctl stop redis
```

## 🔧 Solución de problemas

### Worker no inicia
```bash
# Verificar Redis
redis-cli ping

# Verificar configuración
python3 -c "from app.core.celery_app import celery_app; print('OK')"

# Ver logs detallados
celery -A app.core.celery_app worker --loglevel=debug
```

### Flower no accesible
```bash
# Verificar puerto
netstat -tuln | grep 5555

# Probar local
curl http://localhost:5555

# Verificar firewall
sudo firewall-cmd --list-ports
```

### Redis no conecta
```bash
# Estado del servicio
systemctl status redis

# Logs de Redis
journalctl -u redis -f

# Configuración
cat /etc/redis/redis.conf | grep bind
```

## 📋 Endpoints de la API

### Inscripciones
- `GET /api/v1/inscripciones/` - Listar inscripciones
- `POST /api/v1/inscripciones/` - Crear inscripción
- `GET /api/v1/inscripciones/estudiante/{id}` - Por estudiante

### Cola asíncrona
- `GET /api/v1/queue/workers` - Estado de workers
- `GET /api/v1/queue/queues` - Estado de colas
- `POST /api/v1/queue/inscription` - Inscripción asíncrona
- `POST /api/v1/queue/bulk-inscription` - Inscripción masiva

### Historial
- `GET /api/v1/historial/estudiante/{id}` - Historial de estudiante
- `GET /api/v1/historial/materia/{id}` - Historial de materia

¡Con esta configuración tienes acceso completo a todos los componentes del sistema! 🎉