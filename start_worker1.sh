#!/bin/bash

echo "🐝 Iniciando Worker 1 de Celery..."

# Activar entorno virtual si existe
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Entorno virtual activado"
fi

# Ejecutar worker 1
celery -A app.core.celery_app worker \
    --loglevel=info \
    --hostname=worker1@%h \
    --concurrency=2 \
    --queues=inscripciones,default \
    --logfile=logs/worker1.log

echo "🐝 Worker 1 iniciado en background"