# Prueba de concurrencia y control de cupos en el sistema de inscripción

Este documento describe en detalle cómo funciona el sistema de colas, la asignación de cupos y la prueba de concurrencia realizada para validar la integridad y seguridad del microservicio de inscripción académica.

## 1. Arquitectura del sistema de colas

- **Celery + Redis:** El microservicio utiliza Celery como sistema de colas para procesar inscripciones en segundo plano. Redis actúa como broker y backend, gestionando las tareas y sus resultados.
- **Workers:** Varias instancias de workers Celery procesan las tareas de inscripción de manera concurrente y desacoplada.
- **API FastAPI:** Las solicitudes de inscripción llegan a la API, que encola cada petición como una tarea independiente en Celery.

## 2. Flujo de inscripción y control de concurrencia

1. **Recepción de solicitudes:** Cuando varios estudiantes intentan inscribirse al mismo grupo simultáneamente, cada solicitud se convierte en una tarea Celery y se encola en Redis.
2. **Procesamiento por workers:** Cada worker toma una tarea y ejecuta la lógica de inscripción:
   - Valida existencia del estudiante y periodo.
   - Verifica disponibilidad de cupo en el grupo solicitado.
   - Verifica que no haya conflictos de horario.
3. **Bloqueo de fila en la base de datos:**
   - Para evitar sobrecupos, se utiliza `SELECT ... FOR UPDATE` al consultar y actualizar el cupo del grupo.
   - Este bloqueo garantiza que solo un worker pueda leer y modificar el cupo en ese instante.
   - El primer worker que obtiene el bloqueo inscribe al estudiante y actualiza el contador de inscritos.
   - Los siguientes workers, al obtener el bloqueo después, encuentran que el cupo ya fue ocupado y lanzan una excepción personalizada (`GrupoSinCupoException`).
4. **Resultado y trazabilidad:**
   - El resultado de cada inscripción (éxito o error) se almacena en Redis y puede consultarse vía la API usando el `task_id`.
   - Los logs y las excepciones permiten auditar y monitorear todo el proceso.

## 3. Prueba de concurrencia: Script y resultados

### Script utilizado
Se creó un script en Python que simula inscripciones concurrentes de 10 estudiantes (RA0001 a RA0010) al mismo grupo (`G-ELC108-E`). El script utiliza `requests` y `threading` para enviar todas las solicitudes al mismo tiempo y luego consulta el estado de cada inscripción.

```python
import threading
import requests
import time

API_URL = "http://localhost:8003/api/v1/queue/inscripciones/async-by-groups"
STATUS_URL = "http://localhost:8003/api/v1/queue/tasks/{task_id}/status"

registro_academico_list = [
    "RA0001", "RA0002", "RA0003", "RA0004", "RA0005",
    "RA0006", "RA0007", "RA0008", "RA0009", "RA0010"
]
grupo = "G-ELC108-E"
codigo_periodo = "1-2025"

main_task_ids = []
group_task_ids = []

def inscribir(registro_academico):
    payload = {
        "registro_academico": registro_academico,
        "codigo_periodo": codigo_periodo,
        "grupos": [grupo]
    }
    try:
        response = requests.post(API_URL, json=payload)
        data = response.json()
        print(f"{registro_academico}: {response.status_code} - {data}")
        if response.status_code in (200, 202) and "group_tasks" in data:
            main_task_ids.append(data.get("main_task_id"))
            for gt in data["group_tasks"]:
                group_task_ids.append(gt["task_id"])
    except Exception as e:
        print(f"Error inscribiendo {registro_academico}: {e}")

threads = []
for registro_academico in registro_academico_list:
    t = threading.Thread(target=inscribir, args=(registro_academico,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(f"\nTask IDs a consultar: {group_task_ids}\n")
print("Consultando estado de las inscripciones...")
time.sleep(2)

for task_id in group_task_ids:
    try:
        url = STATUS_URL.format(task_id=task_id)
        response = requests.get(url)
        data = response.json()
        print(f"Task {task_id}: {data['status']} - {data.get('result', data)}")
    except Exception as e:
        print(f"Error consultando estado de {task_id}: {e}")
```

### Resultados obtenidos
- Todas las inscripciones se encolaron y procesaron casi simultáneamente.
- Solo una inscripción fue exitosa, porque el grupo tenía cupos limitados.
- Las demás inscripciones recibieron el mensaje de error: “Grupo 'G-ELC108-E' no tiene cupo disponible”.
- El sistema demostró que maneja correctamente la concurrencia y evita sobrecupos.

## 4. Conclusión

- El sistema de colas (Celery + Redis) permite procesar inscripciones de manera concurrente y segura.
- El uso de bloqueo de fila en la base de datos garantiza que nunca se asignen más cupos de los disponibles, incluso bajo alta concurrencia.
- La prueba realizada valida que el sistema responde correctamente ante múltiples solicitudes simultáneas, garantizando la integridad y trazabilidad de los datos.

---

