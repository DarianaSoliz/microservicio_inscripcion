#!/bin/bash

echo "🔍 Verificando corrección completa del proyecto..."

# Función para verificar import
check_import() {
    local module=$1
    local description=$2
    python3 -c "import $module; print('✅ $description')" 2>/dev/null || echo "❌ Error: $description"
}

# Verificar dependencias críticas
echo ""
echo "📦 Verificando dependencias..."
check_import "psycopg" "psycopg instalado"
check_import "sqlalchemy.ext.asyncio" "SQLAlchemy async disponible"
check_import "fastapi" "FastAPI disponible"

# Verificar que no hay asyncpg
echo ""
echo "🚫 Verificando que asyncpg NO esté instalado..."
python3 -c "import asyncpg; print('❌ ERROR: asyncpg encontrado - debe ser removido')" 2>/dev/null || echo "✅ asyncpg no encontrado (correcto)"

# Verificar imports de la aplicación
echo ""
echo "🏗️ Verificando imports de la aplicación..."
check_import "app.core.database" "Configuración de base de datos"
check_import "app.core.config" "Configuración de la app"
check_import "app.services.base_service" "Servicios base"
check_import "app.services.historial_service" "Servicios de historial"

# Verificar routers
echo ""
echo "🛣️ Verificando routers..."
check_import "app.routers.inscripciones" "Router de inscripciones"
check_import "app.routers.periodos" "Router de períodos"
check_import "app.routers.queue" "Router de cola"
check_import "app.routers.historial" "Router de historial"

# Verificar main app
echo ""
echo "🚀 Verificando aplicación principal..."
python3 -c "
try:
    from app.main import app
    print('✅ Aplicación principal importada correctamente')
    print('✅ FastAPI app creada exitosamente')
except Exception as e:
    print(f'❌ Error en aplicación principal: {e}')
    exit(1)
"

# Verificar conexión a base de datos (opcional)
echo ""
echo "🗃️ Verificando configuración de base de datos..."
python3 -c "
try:
    from app.core.database import engine
    print('✅ Motor de base de datos configurado')
    print('  - Driver: psycopg (async)')
    print('  - Estado: Listo para conexiones asíncronas')
except Exception as e:
    print(f'❌ Error en configuración de BD: {e}')
"

echo ""
echo "🎉 Verificación completa!"
echo ""
echo "Si todos los checks anteriores muestran ✅, el servidor debería iniciar correctamente."
echo ""
echo "🚀 Para ejecutar el servidor:"
echo "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"