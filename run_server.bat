@echo off
REM Script para correr el microservicio directamente con uvicorn en Windows

echo 🚀 Iniciando microservicio en puerto 8003...

REM Activar entorno virtual si existe
if exist ".venv" (
    echo 📦 Activando entorno virtual...
    call .venv\Scripts\activate.bat
)

REM Verificar conexión a base de datos
echo 🔌 Verificando conexión a base de datos...
python -c "import psycopg2; conn = psycopg2.connect('postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require'); print('✅ Base de datos conectada'); conn.close()" || (
    echo ❌ Error de conexión a base de datos
    pause
    exit /b 1
)

REM Iniciar el servidor
echo 🌐 Iniciando servidor en http://0.0.0.0:8003
echo 📖 Documentación disponible en: http://localhost:8003/docs
echo.
echo Presiona Ctrl+C para detener el servidor
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload

pause