"""
DAG: jd_ingest_chassis_daily

Chama a API externa de chassis diariamente às 06:00 e envia os
resultados para o portal Django via POST /api/ingest/.

O portal armazena os chassis em stage (status=pending).
O admin processa via botão "Implementar" no portal.

Variáveis de ambiente necessárias:
  PORTAL_URL       — URL base do portal Django (ex: http://portal:8000)
  PORTAL_API_KEY   — chave de autenticação do endpoint /api/ingest/
  CHASSIS_API_URL  — URL da API externa que retorna os chassis
  CHASSIS_API_KEY  — token/chave da API externa (opcional)
"""

import os
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

PORTAL_URL = os.getenv("PORTAL_URL", "http://portal:8000")
PORTAL_API_KEY = os.getenv("PORTAL_API_KEY", "")
CHASSIS_API_URL = os.getenv("CHASSIS_API_URL", "")
CHASSIS_API_KEY = os.getenv("CHASSIS_API_KEY", "")


def fetch_and_ingest_chassis(**context):
    if not CHASSIS_API_URL:
        raise ValueError("CHASSIS_API_URL não configurada. Verifique o .env do Airflow.")

    # 1. Chama API externa de chassis
    headers = {}
    if CHASSIS_API_KEY:
        headers["Authorization"] = f"Bearer {CHASSIS_API_KEY}"

    resp = requests.get(CHASSIS_API_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    if isinstance(data, dict):
        chassis_list = data.get("chassis", data.get("pins", data.get("data", [])))
    else:
        chassis_list = data

    if not chassis_list:
        print("API externa não retornou chassis. Nada a fazer.")
        return

    print(f"API externa retornou {len(chassis_list)} chassis.")

    # 2. Envia para o portal Django
    portal_resp = requests.post(
        f"{PORTAL_URL}/api/ingest/",
        json={"chassis": chassis_list, "source": "airflow_daily"},
        headers={"X-Api-Key": PORTAL_API_KEY},
        timeout=30,
    )
    portal_resp.raise_for_status()

    result = portal_resp.json()
    print(
        f"Portal: {result['added']} novos chassis adicionados, "
        f"{result['skipped']} já existiam."
    )


default_args = {
    "owner": "maqnelson",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="jd_ingest_chassis_daily",
    default_args=default_args,
    description="Busca chassis da API externa e envia para o portal JD (stage)",
    schedule_interval="0 6 * * *",   # Todo dia às 06:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["jd", "optioncode", "maqnelson"],
) as dag:

    ingest = PythonOperator(
        task_id="fetch_and_ingest_chassis",
        python_callable=fetch_and_ingest_chassis,
    )
