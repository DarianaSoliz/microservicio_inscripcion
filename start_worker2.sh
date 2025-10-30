#!/bin/bash

echo "🐝 Iniciando Worker 2 de Celery..."

# Activar entorno virtual si existe
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Entorno virtual activado"
fi

# Ejecutar worker 2
celery -A app.core.celery_app worker \
    --loglevel=info \
    --hostname=worker2@%h \
    --concurrency=2 \
    --queues=inscripciones,bulk_inscriptions \
    --logfile=logs/worker2.log

echo "🐝 Worker 2 iniciado en background"