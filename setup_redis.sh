#!/bin/bash

echo "🔴 Configurando Redis para el microservicio..."

# Verificar si Redis está instalado
if ! command -v redis-server &> /dev/null; then
    echo "📦 Redis no está instalado. Instalando..."
    
    # Para Fedora/RHEL/CentOS
    if command -v dnf &> /dev/null; then
        sudo dnf install -y redis
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
    else
        echo "❌ No se pudo determinar el gestor de paquetes. Instala Redis manualmente:"
        echo "   Fedora/RHEL: sudo dnf install redis"
        echo "   Ubuntu/Debian: sudo apt install redis-server"
        exit 1
    fi
else
    echo "✅ Redis ya está instalado"
fi

# Iniciar y habilitar Redis
echo "🚀 Iniciando Redis..."
sudo systemctl start redis
sudo systemctl enable redis

# Verificar estado
echo "🔍 Verificando estado de Redis..."
if sudo systemctl is-active --quiet redis; then
    echo "✅ Redis está ejecutándose"
else
    echo "❌ Error: Redis no se pudo iniciar"
    sudo systemctl status redis
    exit 1
fi

# Verificar conectividad
echo "🔌 Verificando conectividad..."
if redis-cli ping | grep -q PONG; then
    echo "✅ Redis responde correctamente"
else
    echo "❌ Error: Redis no responde"
    exit 1
fi

# Mostrar información
echo ""
echo "📋 Información de Redis:"
echo "   Estado: $(sudo systemctl is-active redis)"
echo "   Puerto: 6379"
echo "   URL: redis://localhost:6379/0"

echo ""
echo "🎉 Redis configurado correctamente!"
echo ""
echo "🚀 Ahora puedes ejecutar el microservicio:"
echo "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"