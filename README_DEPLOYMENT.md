# Deployment en Fedora - Python 3.13 Compatible

Este proyecto ha sido adaptado para ser completamente compatible con Python 3.13 en Fedora.

## 🚀 Deployment rápido

### 1. En el servidor Fedora:

```bash
# Clonar repositorio
git clone https://github.com/DarianaSoliz/microservicio_inscripcion.git
cd microservicio_inscripcion

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias compatibles
pip install -r requirements-fedora.txt

# Ejecutar tests de compatibilidad
python3 test_compatibility.py

# Ejecutar deployment
chmod +x deploy.sh monitor.sh
./deploy.sh
```

### 2. Verificar servicios:

```bash
# Ver estado
./monitor.sh

# Logs en tiempo real
journalctl -u inscription-api -f
```

## 🔧 Cambios realizados para compatibilidad:

### Dependencias actualizadas:
- ✅ FastAPI 0.115.0 (compatible con Python 3.13)
- ✅ Pydantic 2.8.2 (compatible con Python 3.13)
- ✅ SQLAlchemy 2.0.35 (compatible con Python 3.13)
- ✅ Uvicorn 0.30.0 (compatible con Python 3.13)
- ❌ AsyncPG removido (reemplazado por psycopg2-binary)

### Arquitectura:
- **app/main_sync.py**: Versión sincrónica del main
- **app/core/database_sync.py**: Versión sincrónica de la base de datos
- **requirements-fedora.txt**: Dependencias compatibles

### URLs disponibles:
- API: http://servidor:8000
- Docs: http://servidor:8000/docs
- Health: http://servidor:8000/health
- Flower: http://servidor:8000/flower

## 🔍 Troubleshooting:

### Si hay errores de conexión DB:
```bash
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require')
print('✅ DB OK')
"
```

### Si hay errores de servicios:
```bash
systemctl status inscription-api
journalctl -u inscription-api -n 50
```

### Restart completo:
```bash
systemctl restart inscription-api celery-worker flower nginx
```