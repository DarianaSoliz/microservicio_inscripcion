
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
time.sleep(2)  # Espera breve para que las tareas se procesen

for task_id in group_task_ids:
    try:
        url = STATUS_URL.format(task_id=task_id)
        response = requests.get(url)
        data = response.json()
        print(f"Task {task_id}: {data['status']} - {data.get('result', data)}")
    except Exception as e:
        print(f"Error consultando estado de {task_id}: {e}")
