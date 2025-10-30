#!/bin/bash

# Script de monitoreo y mantenimiento
set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Función para verificar servicio
check_service() {
    local service=$1
    if sudo systemctl is-active --quiet $service; then
        print_status "$service está funcionando"
        return 0
    else
        print_error "$service NO está funcionando"
        return 1
    fi
}

# Función para verificar conexión HTTP
check_http() {
    local url=$1
    local name=$2
    if curl -s -f "$url" > /dev/null; then
        print_status "$name responde correctamente"
        return 0
    else
        print_error "$name NO responde"
        return 1
    fi
}

# Verificar servicios
print_header "Estado de Servicios"
services=("redis" "inscription-api" "celery-worker" "flower" "nginx")
failed_services=()

for service in "${services[@]}"; do
    if ! check_service $service; then
        failed_services+=($service)
    fi
done

# Verificar endpoints
print_header "Estado de Endpoints"
endpoints=(
    "http://localhost:8000/health|API Health"
    "http://localhost:8000/|API Root"
    "http://localhost:5555|Flower"
)

for endpoint in "${endpoints[@]}"; do
    IFS='|' read -r url name <<< "$endpoint"
    check_http "$url" "$name"
done

# Verificar Redis
print_header "Estado de Redis"
if redis-cli ping | grep -q PONG; then
    print_status "Redis responde correctamente"
else
    print_error "Redis no responde"
fi

# Verificar base de datos
print_header "Estado de Base de Datos"
cd /root/microservicio_inscripcion
source .venv/bin/activate

python3 -c "
import sys
from app.core.database_sync import engine

try:
    with engine.begin() as conn:
        result = conn.exec_driver_sql('SELECT 1')
        print('✅ Base de datos conectada')
        sys.exit(0)
except Exception as e:
    print(f'❌ Error de base de datos: {e}')
    sys.exit(1)
"

# Verificar carga del sistema
print_header "Recursos del Sistema"
echo "📊 Uso de CPU y Memoria:"
top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "CPU Usage: " 100 - $1 "%"}'
free -h | awk 'NR==2{printf "Memory Usage: %.1f%%\n", $3/$2 * 100.0}'

echo ""
echo "💾 Uso de disco:"
df -h / | awk 'NR==2{printf "Disk Usage: %s/%s (%s)\n", $3, $2, $5}'

# Verificar logs recientes
print_header "Logs Recientes (Últimos 5 errores)"
echo "🔍 FastAPI:"
sudo journalctl -u inscription-api --since "1 hour ago" | grep -i error | tail -5 || echo "No errors found"

echo ""
echo "🔍 Celery:"
sudo journalctl -u celery-worker --since "1 hour ago" | grep -i error | tail -5 || echo "No errors found"

# Resumen
print_header "Resumen"
if [ ${#failed_services[@]} -eq 0 ]; then
    print_status "Todos los servicios están funcionando correctamente"
else
    print_error "Servicios con problemas: ${failed_services[*]}"
    echo ""
    echo "🔧 Para reiniciar servicios problemáticos:"
    for service in "${failed_services[@]}"; do
        echo "   sudo systemctl restart $service"
    done
fi

echo ""
echo "📖 Comandos útiles:"
echo "   - Ver logs en tiempo real: sudo journalctl -u inscription-api -f"
echo "   - Reiniciar todos los servicios: sudo systemctl restart inscription-api celery-worker flower"
echo "   - Ver estado detallado: sudo systemctl status inscription-api"