import os
import re
from pathlib import Path

import pandas as pd

from app_paths import app_dir

APP_DIR = app_dir()
PASTA_SINAPI_PROCESSADO = os.path.join(APP_DIR, "sinapi", "sinapi_processado")
CAMINHO_FALLBACK_SINAPI = os.path.join(APP_DIR, "sinapi_precos.csv")


def _parse_referencia_do_nome_csv(nome_arquivo):
    m = re.match(
        r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.csv$",
        nome_arquivo.strip(),
    )
    if not m:
        return None
    ano, mes = int(m.group(1)), int(m.group(2))
    if not (1 <= mes <= 12):
        return None
    return ano, mes


def obter_csv_sinapi_mais_recente(pasta_processado):
    if not os.path.isdir(pasta_processado):
        return None, None
    candidatos = []
    for nome in os.listdir(pasta_processado):
        if not nome.lower().endswith(".csv"):
            continue
        tupla_data = _parse_referencia_do_nome_csv(nome)
        if tupla_data:
            candidatos.append(
                (tupla_data, os.path.join(pasta_processado, nome), nome)
            )
    if not candidatos:
        return None, None
    candidatos.sort(key=lambda x: x[0], reverse=True)
    (ano, mes), caminho, _ = candidatos[0]
    rotulo = f"{mes:02d}/{ano}"
    return caminho, rotulo


def carregar_sinapi_por_caminho(caminho, rotulo):
    sinapi = pd.read_csv(caminho, dtype={"codigo": str})
    sinapi.columns = sinapi.columns.str.strip().str.lower()
    return sinapi, caminho, rotulo


def carregar_sinapi_inicial():
    caminho, rotulo = obter_csv_sinapi_mais_recente(PASTA_SINAPI_PROCESSADO)

    if caminho is None and os.path.isfile(CAMINHO_FALLBACK_SINAPI):
        caminho = CAMINHO_FALLBACK_SINAPI
        rotulo = "arquivo local (sinapi_precos.csv na raiz do projeto)"

    if caminho is None:
        sinapi = pd.DataFrame(
            columns=["codigo", "descricao", "unidade", "estado", "custo"]
        )
        return sinapi, None, "BASE AUSENTE"

    sinapi, caminho, rotulo = carregar_sinapi_por_caminho(caminho, rotulo)
    return sinapi, caminho, rotulo


def recarregar_sinapi():
    caminho, rotulo = obter_csv_sinapi_mais_recente(PASTA_SINAPI_PROCESSADO)

    if caminho is None and os.path.isfile(CAMINHO_FALLBACK_SINAPI):
        caminho = CAMINHO_FALLBACK_SINAPI
        rotulo = "arquivo local (sinapi_precos.csv na raiz do projeto)"

    if caminho is None:
        sinapi = pd.DataFrame(
            columns=["codigo", "descricao", "unidade", "estado", "custo"]
        )
        return sinapi, None, "BASE AUSENTE"

    return carregar_sinapi_por_caminho(caminho, rotulo)


PADRAO_XLSX_REFERENCIA = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.xlsx$"
)


def obter_xlsx_sinapi_referencia_mais_recente():
    pasta = Path(app_dir()) / "sinapi" / "sinapi_referencia"
    if not pasta.is_dir():
        return None
    candidatos = []
    for arquivo in pasta.glob("*.xlsx"):
        if arquivo.name.startswith("~$"):
            continue
        match = PADRAO_XLSX_REFERENCIA.match(arquivo.name)
        if match:
            candidatos.append(
                ((int(match.group(1)), int(match.group(2))), arquivo)
            )
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1]


def obter_estados_da_sinapi(sinapi):
    if sinapi.empty or "estado" not in sinapi.columns:
        return []
    return sorted(sinapi["estado"].dropna().unique().tolist())
