#!/bin/bash

# Script para correr el microservicio directamente con uvicorn

echo "🚀 Iniciando microservicio en puerto 8003..."

# Activar entorno virtual si existe
if [ -d ".venv" ]; then
    echo "📦 Activando entorno virtual..."
    source .venv/bin/activate
fi

# Verificar que las dependencias estén instaladas
echo "🔍 Verificando dependencias..."
python3 -c "import fastapi, uvicorn, psycopg2" 2>/dev/null || {
    echo "❌ Faltan dependencias. Instalando..."
    pip install -r requirements-fedora.txt
}

# Verificar conexión a base de datos
echo "🔌 Verificando conexión a base de datos..."
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require')
    print('✅ Base de datos conectada')
    conn.close()
except Exception as e:
    print(f'❌ Error de conexión: {e}')
    exit(1)
"

# Iniciar el servidor
echo "🌐 Iniciando servidor en http://0.0.0.0:8003"
echo "📖 Documentación disponible en: http://localhost:8003/docs"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload