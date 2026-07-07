import os
import re
from pathlib import Path

import pandas as pd

from app_paths import app_dir
from core.sinapi_base import SinapiBase

APP_DIR = app_dir()
PASTA_SINAPI_PROCESSADO = os.path.join(APP_DIR, "sinapi", "sinapi_processado")

PADRAO_CATALOGO = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})_catalogo\.csv$"
)
PADRAO_PRECOS = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})_precos\.csv$"
)
PADRAO_MONOLITICO_OBSOLETO = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.csv$"
)
PADRAO_XLSX_REFERENCIA = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.xlsx$"
)


def _rotulo_referencia(ano: int, mes: int) -> str:
    return f"{mes:02d}/{ano}"


def _listar_pares_processados(pasta_processado: str) -> dict[tuple[int, int], tuple[str, str]]:
    if not os.path.isdir(pasta_processado):
        return {}
    catalogos: dict[tuple[int, int], str] = {}
    precos: dict[tuple[int, int], str] = {}
    for nome in os.listdir(pasta_processado):
        if not nome.lower().endswith(".csv"):
            continue
        caminho = os.path.join(pasta_processado, nome)
        match_cat = PADRAO_CATALOGO.match(nome)
        if match_cat:
            catalogos[(int(match_cat.group(1)), int(match_cat.group(2)))] = caminho
            continue
        match_pre = PADRAO_PRECOS.match(nome)
        if match_pre:
            precos[(int(match_pre.group(1)), int(match_pre.group(2)))] = caminho
    return {
        chave: (catalogos[chave], precos[chave])
        for chave in catalogos.keys() & precos.keys()
    }


def _remover_csv_monolitico_obsoleto(pasta_processado: str) -> None:
    if not os.path.isdir(pasta_processado):
        return
    for nome in os.listdir(pasta_processado):
        if not PADRAO_MONOLITICO_OBSOLETO.match(nome):
            continue
        if "_catalogo" in nome.lower() or "_precos" in nome.lower():
            continue
        try:
            os.remove(os.path.join(pasta_processado, nome))
        except OSError:
            pass


def _garantir_csv_processado(pasta_processado: str) -> None:
    if _listar_pares_processados(pasta_processado):
        return
    xlsx = obter_xlsx_sinapi_referencia_mais_recente()
    if xlsx is None:
        return
    from sinapi.extrair_sinapi import processar_arquivo

    try:
        processar_arquivo(xlsx)
    except Exception as exc:
        print("Erro ao processar planilha SINAPI inicial:", exc)


def carregar_sinapi_por_referencia(pasta_processado=PASTA_SINAPI_PROCESSADO):
    try:
        _remover_csv_monolitico_obsoleto(pasta_processado)
        _garantir_csv_processado(pasta_processado)

        pares = _listar_pares_processados(pasta_processado)
        if not pares:
            return SinapiBase.vazio(), None, "BASE AUSENTE"

        chave = max(pares.keys())
        caminho_catalogo, caminho_precos = pares[chave]
        rotulo = _rotulo_referencia(chave[0], chave[1])
        return _carregar_par(caminho_catalogo, caminho_precos, rotulo)
    except Exception as exc:
        print("Erro ao carregar base SINAPI:", exc)
        return SinapiBase.vazio(), None, "BASE AUSENTE"


def obter_csv_sinapi_mais_recente(pasta_processado=PASTA_SINAPI_PROCESSADO):
    """Retorna o catálogo CSV do par mais recente (catálogo + preços)."""
    pares = _listar_pares_processados(pasta_processado)
    if not pares:
        return None, None
    chave = max(pares.keys())
    caminho_catalogo, _caminho_precos = pares[chave]
    return caminho_catalogo, _rotulo_referencia(chave[0], chave[1])


def _carregar_par(caminho_catalogo: str, caminho_precos: str, rotulo: str):
    catalogo = pd.read_csv(
        caminho_catalogo,
        dtype={"codigo": str},
        usecols=lambda c: c.strip().lower() in {"codigo", "descricao", "unidade", "tipo"},
    )
    precos = pd.read_csv(
        caminho_precos,
        dtype={"codigo": str},
        usecols=lambda c: c.strip().lower() in {"codigo", "estado", "custo"},
    )
    base = SinapiBase(catalogo, precos)
    return base, caminho_catalogo, rotulo


def carregar_sinapi_inicial():
    return carregar_sinapi_por_referencia()


def recarregar_sinapi():
    return carregar_sinapi_por_referencia()


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


def obter_estados_da_sinapi(sinapi: SinapiBase):
    if sinapi.empty:
        return []
    return sinapi.estados()
