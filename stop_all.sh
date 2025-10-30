#!/bin/bash

echo "🛑 Parando sistema completo del microservicio"
echo "=========================================="

# Función para parar proceso por PID
stop_process() {
    local name=$1
    local pidfile="pids/${name}.pid"
    
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null 2>&1; then
            echo "🔄 Parando $name (PID: $pid)..."
            kill $pid
            sleep 2
            if ps -p $pid > /dev/null 2>&1; then
                echo "⚠️ Forzando parada de $name..."
                kill -9 $pid
            fi
            echo "✅ $name parado"
        else
            echo "ℹ️ $name ya estaba parado"
        fi
        rm -f "$pidfile"
    else
        echo "ℹ️ No se encontró PID para $name"
    fi
}

echo ""
echo "1️⃣ Parando Flower..."
stop_process "flower"

echo ""
echo "2️⃣ Parando Workers de Celery..."
stop_process "worker1"
stop_process "worker2"

# Parar cualquier worker restante
echo ""
echo "🧹 Limpiando workers restantes..."
pkill -f "celery.*worker" && echo "✅ Workers adicionales parados" || echo "ℹ️ No hay workers adicionales"

echo ""
echo "3️⃣ Información de Redis..."
if systemctl is-active --quiet redis; then
    echo "🔴 Redis sigue funcionando (normal - no se para automáticamente)"
    echo "   Para parar Redis: sudo systemctl stop redis"
else
    echo "🔴 Redis ya estaba parado"
fi

echo ""
echo "4️⃣ Verificando puertos..."
for port in 5555 8003; do
    if netstat -tuln | grep -q ":$port "; then
        echo "⚠️ Puerto $port aún en uso"
    else
        echo "✅ Puerto $port liberado"
    fi
done

echo ""
echo "🧹 Limpiando archivos temporales..."
rm -rf pids/

echo ""
echo "✅ Sistema parado completamente!"
echo ""
echo "ℹ️ Para reiniciar:"
echo "  ./start_all.sh"
echo ""
echo "ℹ️ Para parar Redis (opcional):"
echo "  sudo systemctl stop redis"