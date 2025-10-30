#!/bin/bash

echo "🔄 Instalando dependencias para Python 3.13 con soporte asíncrono..."

# Instalar dependencias
pip install -r requirements-async-py313.txt

echo "✅ Dependencias instaladas correctamente"

# Verificar instalación
echo "🔍 Verificando instalación..."
python -c "
import asyncpg
print('❌ Error: asyncpg fue encontrado, debería usar psycopg')
" 2>/dev/null || echo "✅ asyncpg no está instalado (correcto)"

python -c "
import psycopg
print('✅ psycopg instalado correctamente')
" 2>/dev/null || echo "❌ Error: psycopg no está instalado"

python -c "
from sqlalchemy.ext.asyncio import AsyncSession
print('✅ SQLAlchemy async importado correctamente')
" 2>/dev/null || echo "❌ Error: SQLAlchemy async no se puede importar"

python -c "
import fastapi
print(f'✅ FastAPI {fastapi.__version__} instalado')
" 2>/dev/null || echo "❌ Error: FastAPI no está instalado"

echo "🚀 ¡Listo para ejecutar el servidor!"
echo "Ejecuta: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"