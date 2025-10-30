#!/bin/bash

# Script de deployment para Fedora DigitalOcean
set -e

echo "🚀 Iniciando deployment del microservicio de inscripciones..."

# Variables
PROJECT_DIR="/root/microservicio_inscripcion"
VENV_DIR="$PROJECT_DIR/.venv"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Actualizar el código
print_status "Actualizando código desde Git..."
cd $PROJECT_DIR
git pull origin master

# 2. Activar entorno virtual e instalar dependencias
print_status "Instalando dependencias..."
source $VENV_DIR/bin/activate
pip install -r requirements-fedora.txt

# 3. Copiar archivos de configuración
print_status "Configurando servicios systemd..."

# Crear directorio para PID de Celery
sudo mkdir -p /var/run/celery
sudo chown root:root /var/run/celery

# Copiar archivos de servicio
sudo cp $PROJECT_DIR/inscription-api.service /etc/systemd/system/
sudo cp $PROJECT_DIR/celery-worker.service /etc/systemd/system/
sudo cp $PROJECT_DIR/flower.service /etc/systemd/system/

# 4. Configurar Nginx
print_status "Configurando Nginx..."

# Crear directorio SSL si no existe
sudo mkdir -p /etc/nginx/ssl

# Generar certificado self-signed temporal (reemplazar con Let's Encrypt)
if [ ! -f /etc/nginx/ssl/nginx-selfsigned.crt ]; then
    print_warning "Generando certificado SSL temporal..."
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/nginx-selfsigned.key \
        -out /etc/nginx/ssl/nginx-selfsigned.crt \
        -subj "/C=BO/ST=State/L=City/O=Organization/CN=localhost"
fi

# Copiar configuración de Nginx
sudo cp $PROJECT_DIR/nginx-inscription.conf /etc/nginx/conf.d/

# Verificar configuración de Nginx
sudo nginx -t

# 5. Recargar systemd y servicios
print_status "Recargando servicios..."
sudo systemctl daemon-reload

# 6. Habilitar servicios
print_status "Habilitando servicios..."
sudo systemctl enable inscription-api
sudo systemctl enable celery-worker
sudo systemctl enable flower
sudo systemctl enable nginx
sudo systemctl enable redis

# 7. Reiniciar servicios
print_status "Reiniciando servicios..."
sudo systemctl restart redis
sudo systemctl restart inscription-api
sudo systemctl restart celery-worker
sudo systemctl restart flower
sudo systemctl restart nginx

# 8. Verificar estado de servicios
print_status "Verificando estado de servicios..."

services=("redis" "inscription-api" "celery-worker" "flower" "nginx")

for service in "${services[@]}"; do
    if sudo systemctl is-active --quiet $service; then
        print_status "$service está funcionando"
    else
        print_error "$service NO está funcionando"
        sudo systemctl status $service --no-pager -l
    fi
done

# 9. Mostrar información de deployment
print_status "Deployment completado!"
echo ""
echo "📋 Información de servicios:"
echo "🌐 API Principal: https://tu_dominio.com"
echo "📊 Flower (Monitoring): https://tu_dominio.com/flower"
echo "🔧 Health Check: https://tu_dominio.com/health"
echo "📖 Documentación: https://tu_dominio.com/docs"
echo ""
echo "📂 Logs importantes:"
echo "   - FastAPI: sudo journalctl -u inscription-api -f"
echo "   - Celery: sudo journalctl -u celery-worker -f"
echo "   - Flower: sudo journalctl -u flower -f"
echo "   - Nginx: sudo tail -f /var/log/nginx/inscription_error.log"
echo ""
echo "🔍 Comandos útiles:"
echo "   - Reiniciar API: sudo systemctl restart inscription-api"
echo "   - Reiniciar Workers: sudo systemctl restart celery-worker"
echo "   - Ver estado: sudo systemctl status inscription-api"
echo "   - Ver logs: sudo journalctl -u inscription-api -f"