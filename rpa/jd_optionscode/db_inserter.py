import os
from datetime import datetime

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_INSERT_SQL = """
    INSERT INTO tb_EquipmentOptions
        (pin, code, description, created_at, created_by,
         deleted_at, deleted_by, created_at_db, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        description = VALUES(description),
        deleted_at  = VALUES(deleted_at),
        deleted_by  = VALUES(deleted_by),
        updated_at  = VALUES(updated_at)
"""


def _val(v):
    """Converte valor para string ou None se vazio/nulo."""
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    if s.lower() in ('', 'nan', 'nat', 'none'):
        return None
    return s.replace('\uFFFD', '')


def inserir_no_banco(df: pd.DataFrame) -> int:
    """
    Insere/atualiza registros na tabela tb_EquipmentOptions via MySQL.

    Args:
        df: DataFrame com colunas: pin, code, description, created, created by,
            deleted, deleted by (padrão do Excel da API JD)

    Returns:
        Número de linhas processadas.

    Raises:
        ValueError: se credenciais MySQL não estiverem configuradas
        mysql.connector.Error: em caso de erro de banco
    """
    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if not all([host, user, password, database]):
        raise ValueError(
            "Credenciais MySQL incompletas. "
            "Configure DB_HOST, DB_USER, DB_PASSWORD, DB_NAME no .env"
        )

    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    agora = datetime.now()

    conn = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        connect_timeout=10,
        charset="utf8mb4",
    )
    cursor = conn.cursor()
    inseridos = 0

    try:
        for _, row in df.iterrows():
            cursor.execute(_INSERT_SQL, (
                _val(row.get("pin")),
                _val(row.get("code")),
                _val(row.get("description")),
                _val(row.get("created")),
                _val(row.get("created by")),
                _val(row.get("deleted")),
                _val(row.get("deleted by")),
                agora,
                agora,
            ))
            inseridos += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return inseridos
