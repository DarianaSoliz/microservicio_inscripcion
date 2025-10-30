#!/bin/bash

echo "🚀 Iniciando sistema completo del microservicio"
echo "=============================================="

# Función para verificar si un puerto está en uso
check_port() {
    local port=$1
    if netstat -tuln | grep -q ":$port "; then
        return 0  # Puerto en uso
    else
        return 1  # Puerto libre
    fi
}

# Función para ejecutar comando en background y guardar PID
run_background() {
    local command="$1"
    local name="$2"
    local logfile="$3"
    
    echo "🔄 Iniciando $name..."
    nohup $command > "$logfile" 2>&1 &
    local pid=$!
    echo $pid > "pids/${name}.pid"
    echo "✅ $name iniciado (PID: $pid, Log: $logfile)"
}

# Crear directorio para PIDs y logs
mkdir -p pids logs

echo ""
echo "1️⃣ Verificando y iniciando Redis..."
if ! systemctl is-active --quiet redis; then
    sudo systemctl start redis
    sleep 2
fi

if redis-cli ping | grep -q PONG; then
    echo "✅ Redis funcionando"
else
    echo "❌ Error: Redis no responde"
    exit 1
fi

echo ""
echo "2️⃣ Iniciando Workers de Celery..."

# Worker 1
run_background "celery -A app.core.celery_app worker --loglevel=info --hostname=worker1@%h --concurrency=2 --queues=inscripciones,default" "worker1" "logs/worker1.log"

sleep 3

# Worker 2  
run_background "celery -A app.core.celery_app worker --loglevel=info --hostname=worker2@%h --concurrency=2 --queues=inscripciones,bulk_inscriptions" "worker2" "logs/worker2.log"

sleep 3

echo ""
echo "3️⃣ Iniciando Flower..."
run_background "celery -A app.core.celery_app flower --port=5555 --host=0.0.0.0 --broker=redis://localhost:6379/0" "flower" "logs/flower.log"

sleep 3

echo ""
echo "4️⃣ Verificando estado del sistema..."

# Verificar Workers
echo "🐝 Workers de Celery:"
celery -A app.core.celery_app inspect active 2>/dev/null | grep -q "worker" && echo "  ✅ Workers activos" || echo "  ⏳ Workers iniciando..."

# Verificar Flower
if check_port 5555; then
    echo "🌸 Flower: ✅ Funcionando en puerto 5555"
else
    echo "🌸 Flower: ⏳ Iniciando..."
fi

# Verificar API principal
if check_port 8003; then
    echo "🌐 API Principal: ✅ Funcionando en puerto 8003"
else
    echo "🌐 API Principal: ❌ No iniciada - ejecutar separadamente"
fi

echo ""
echo "🎉 Sistema iniciado!"
echo "================="
echo ""
echo "📊 URLs de acceso:"
echo "  🌐 API Principal: http://0.0.0.0:8003"
echo "  📋 Documentación: http://0.0.0.0:8003/docs"
echo "  ❤️ Health Check: http://0.0.0.0:8003/health"
echo "  🌸 Flower: http://0.0.0.0:5555"
echo ""
echo "🔧 Comandos útiles:"
echo "  Ver workers: celery -A app.core.celery_app inspect active"
echo "  Ver colas: celery -A app.core.celery_app inspect active_queues"
echo "  Monitor Redis: ./monitor_redis.sh"
echo "  Parar todo: ./stop_all.sh"
echo ""
echo "📝 Logs en:"
echo "  Worker 1: logs/worker1.log"
echo "  Worker 2: logs/worker2.log"
echo "  Flower: logs/flower.log"
echo ""
echo "⚠️ Para iniciar la API principal ejecuta separadamente:"
echo "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"