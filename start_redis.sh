#!/bin/bash

echo "🔴 Configurando Redis para el microservicio..."

# Instalar Redis si no está
if ! command -v redis-server &> /dev/null; then
    echo "Instalando Redis..."
    sudo dnf install -y redis
fi

# Configurar Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verificar
redis-cli ping

echo "✅ Redis configurado en localhost:6379"