@echo off
echo 🔄 Instalando dependencias para Python 3.13 con soporte asíncrono...

REM Instalar dependencias
pip install -r requirements-async-py313.txt

echo ✅ Dependencias instaladas correctamente

REM Verificar instalación
echo 🔍 Verificando instalación...

python -c "import psycopg; print('✅ psycopg instalado correctamente')" 2>nul || echo ❌ Error: psycopg no está instalado

python -c "from sqlalchemy.ext.asyncio import AsyncSession; print('✅ SQLAlchemy async importado correctamente')" 2>nul || echo ❌ Error: SQLAlchemy async no se puede importar

python -c "import fastapi; print(f'✅ FastAPI {fastapi.__version__} instalado')" 2>nul || echo ❌ Error: FastAPI no está instalado

echo 🚀 ¡Listo para ejecutar el servidor!
echo Ejecuta: python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload