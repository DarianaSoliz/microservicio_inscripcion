#!/usr/bin/env python3
"""
Test simple para verificar compatibilidad con Python 3.13
"""
import sys
import psycopg2
from fastapi import FastAPI

def test_basic_imports():
    """Test de imports básicos"""
    try:
        from app.core.config import settings
        from app.core.database_sync import engine, SessionLocal
        print("✅ Imports básicos exitosos")
        return True
    except ImportError as e:
        print(f"❌ Error en imports: {e}")
        return False

def test_database_connection():
    """Test de conexión a base de datos"""
    try:
        conn = psycopg2.connect(
            'postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require'
        )
        cur = conn.cursor()
        cur.execute('SELECT VERSION()')
        version = cur.fetchone()[0]
        print(f"✅ Conexión DB exitosa: {version[:50]}...")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error de conexión DB: {e}")
        return False

def test_fastapi_app():
    """Test de creación de app FastAPI"""
    try:
        from app.main_sync import app
        print(f"✅ FastAPI app creada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error creando app FastAPI: {e}")
        return False

def main():
    """Ejecutar todos los tests"""
    print(f"🐍 Python version: {sys.version}")
    print("🧪 Ejecutando tests de compatibilidad...\n")
    
    tests = [
        ("Imports básicos", test_basic_imports),
        ("Conexión DB", test_database_connection),
        ("FastAPI App", test_fastapi_app),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing {name}...")
        result = test_func()
        results.append(result)
        print()
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"📊 Resultados: {success_count}/{total_count} tests exitosos")
    
    if success_count == total_count:
        print("🎉 Todos los tests pasaron! El proyecto está listo para deployment.")
        return 0
    else:
        print("⚠️  Algunos tests fallaron. Revisar configuración.")
        return 1

if __name__ == "__main__":
    sys.exit(main())