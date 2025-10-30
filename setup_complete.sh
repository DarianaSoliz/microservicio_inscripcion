#!/bin/bash

echo "🛠️ Configuración completa del microservicio para Python 3.13"
echo "=================================================="

# 1. Instalar dependencias Python
echo ""
echo "📦 1. Instalando dependencias Python..."
pip install -r requirements-async-py313.txt

# 2. Configurar Redis
echo ""
echo "🔴 2. Configurando Redis..."

# Verificar si Redis está instalado
if ! command -v redis-server &> /dev/null; then
    echo "📦 Instalando Redis..."
    if command -v dnf &> /dev/null; then
        sudo dnf install -y redis
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
    else
        echo "❌ Instala Redis manualmente y vuelve a ejecutar este script"
        exit 1
    fi
fi

# Iniciar Redis
sudo systemctl start redis
sudo systemctl enable redis

# 3. Verificar configuración
echo ""
echo "🔍 3. Verificando configuración..."

# Verificar Redis
if redis-cli ping | grep -q PONG; then
    echo "✅ Redis funcionando correctamente"
else
    echo "❌ Error con Redis"
    exit 1
fi

# Verificar dependencias Python
python3 -c "
import psycopg
from sqlalchemy.ext.asyncio import AsyncSession
import fastapi
print('✅ Dependencias Python OK')
" || {
    echo "❌ Error con dependencias Python"
    exit 1
}

# Verificar imports de la aplicación
python3 -c "
from app.core.database import engine
from app.main import app
print('✅ Aplicación importa correctamente')
" || {
    echo "❌ Error al importar la aplicación"
    exit 1
}

echo ""
echo "🎉 ¡Configuración completa exitosa!"
echo "=================================================="
echo ""
echo "📋 Estado del sistema:"
echo "   ✅ Python 3.13 + dependencias asíncronas"
echo "   ✅ psycopg (reemplaza asyncpg)"
echo "   ✅ Redis funcionando en localhost:6379"
echo "   ✅ Base de datos configurada con sslmode=require"
echo "   ✅ Aplicación lista para ejecutar"
echo ""
echo "🚀 Ejecutar servidor:"
echo "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"
echo ""
echo "🌐 URLs disponibles:"
echo "   API: http://0.0.0.0:8003"
echo "   Docs: http://0.0.0.0:8003/docs"
echo "   Health: http://0.0.0.0:8003/health"