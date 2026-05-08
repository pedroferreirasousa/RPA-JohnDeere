import io

import pandas as pd
import requests

JD_API_URL = (
    "https://jdwarrantysystem.deere.com/api/products/{pin}/options"
    "?export=EXCEL&language=EN"
)


def processar_chassi(pin: str, token: str) -> int:
    """
    Baixa o Excel de opções do chassi via API JD e insere no MySQL.

    Args:
        pin: número do chassi (VIN/PIN)
        token: Bearer token completo (ex: "Bearer eyJ...")

    Returns:
        Número de linhas inseridas/atualizadas no banco.

    Raises:
        RuntimeError: se a API retornar status != 200
        Exception: qualquer erro de leitura do Excel ou inserção no banco
    """
    url = JD_API_URL.format(pin=pin.strip())
    headers = {"Authorization": token}

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"API retornou {response.status_code} para chassi {pin}: {response.text[:300]}"
        )

    df = pd.read_excel(io.BytesIO(response.content), engine="openpyxl")
    df["CHASSI_REFERENCIA"] = pin.strip()

    from rpa.jd_optionscode.db_inserter import inserir_no_banco
    return inserir_no_banco(df)
