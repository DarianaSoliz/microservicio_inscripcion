#!/bin/bash

echo "🔴 Monitor de Redis"
echo "=================="

# Información general
echo "📋 Estado de Redis:"
systemctl is-active redis && echo "✅ Redis activo" || echo "❌ Redis inactivo"

# Información de conexión
echo ""
echo "🔌 Información de conexión:"
redis-cli info server | grep -E "redis_version|uptime_in_seconds|connected_clients"

# Información de memoria
echo ""
echo "💾 Uso de memoria:"
redis-cli info memory | grep -E "used_memory_human|used_memory_peak_human"

# Información de colas
echo ""
echo "📋 Colas de Celery:"
redis-cli keys "celery*" | head -10

# Estadísticas en tiempo real (opcional)
echo ""
echo "📊 Monitoreo en tiempo real (presiona Ctrl+C para salir):"
echo "Comando: redis-cli monitor"
echo ""

# Menú de opciones
echo "Opciones disponibles:"
echo "1. Ver todas las claves: redis-cli keys '*'"
echo "2. Monitor en tiempo real: redis-cli monitor"
echo "3. Información completa: redis-cli info"
echo "4. Limpiar base de datos: redis-cli flushdb"