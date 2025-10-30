#!/bin/bash

echo "🌸 Iniciando Flower (Monitor de Celery)..."

# Activar entorno virtual si existe
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Entorno virtual activado"
fi

# Instalar Flower si no está
pip install flower

# Ejecutar Flower
celery -A app.core.celery_app flower \
    --port=5555 \
    --host=0.0.0.0 \
    --broker=redis://localhost:6379/0 \
    --basic_auth=admin:password

echo ""
echo "🌸 Flower iniciado!"
echo "📊 URL: http://0.0.0.0:5555"
echo "🔐 Usuario: admin"
echo "🔐 Contraseña: password"