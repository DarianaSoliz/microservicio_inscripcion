import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_connection():
    try:
        # Usar la URL de conexión completa
        database_url = os.getenv('DATABASE_URL', 'postgresql://avnadmin:AVNS_6kmcp-nNyDI2rk7mUHg@topicos-xd.i.aivencloud.com:18069/defaultdb?sslmode=require')
        
        print("Intentando conectar a la base de datos...")
        conn = psycopg2.connect(database_url)
        
        query_sql = 'SELECT VERSION()'
        
        cur = conn.cursor()
        cur.execute(query_sql)
        
        version = cur.fetchone()[0]
        print(f"✅ Conexión exitosa!")
        print(f"Versión de PostgreSQL: {version}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    test_connection()