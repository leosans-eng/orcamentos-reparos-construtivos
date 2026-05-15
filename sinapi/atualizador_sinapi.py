from pathlib import Path
import sys
import requests
import zipfile
import io
import re
from datetime import datetime
import json

# ==========================================
# PASTAS
# ==========================================

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

PASTA_REFERENCIA = BASE_DIR / "sinapi_referencia"
PASTA_PROCESSADO = BASE_DIR / "sinapi_processado"

STATUS_FILE = BASE_DIR / "status.json"

PASTA_REFERENCIA.mkdir(parents=True, exist_ok=True)
PASTA_PROCESSADO.mkdir(parents=True, exist_ok=True)

# ==========================================
# PADRÕES
# ==========================================

PADRAO_ARQUIVO = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.csv$"
)

# ==========================================
# STATUS
# ==========================================

def salvar_status(dados):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# ==========================================
# DESCOBRE ÚLTIMA VERSÃO LOCAL
# ==========================================

def descobrir_ultima_versao_local():
    versoes = []

    for arquivo in PASTA_PROCESSADO.glob("*.csv"):

        match = PADRAO_ARQUIVO.match(arquivo.name)

        if match:
            ano = int(match.group(1))
            mes = int(match.group(2))

            versoes.append((ano, mes))

    if not versoes:
        return None

    return max(versoes)

# ==========================================
# AVANÇA MÊS
# ==========================================

def avancar_mes(ano, mes):

    mes += 1

    if mes > 12:
        mes = 1
        ano += 1

    return ano, mes

# ==========================================
# GERA URL
# ==========================================

def gerar_url(ano, mes):

    mes_str = f"{mes:02d}"

    return (
        f"https://www.caixa.gov.br/Downloads/"
        f"sinapi-relatorios-mensais/"
        f"SINAPI-{ano}-{mes_str}-formato-xlsx.zip"
    )

# ==========================================
# TESTA EXISTÊNCIA
# ==========================================

def sinapi_existe(ano, mes):

    url = gerar_url(ano, mes)

    try:
        response = requests.head(url, timeout=10)

        return response.status_code == 200

    except requests.RequestException:
        return False

# ==========================================
# BAIXA E EXTRAI XLSX
# ==========================================

def baixar_e_extrair(ano, mes):

    url = gerar_url(ano, mes)

    mes_str = f"{mes:02d}"

    nome_xlsx = f"SINAPI_Referência_{ano}_{mes_str}.xlsx"

    response = requests.get(url, timeout=60)

    response.raise_for_status()

    zip_file = zipfile.ZipFile(io.BytesIO(response.content))

    arquivo_encontrado = None

    for nome in zip_file.namelist():

        if nome_xlsx in nome:
            arquivo_encontrado = nome
            break

    if not arquivo_encontrado:
        raise FileNotFoundError(
            f"{nome_xlsx} não encontrado no ZIP."
        )

    caminho_saida = PASTA_REFERENCIA / nome_xlsx

    with zip_file.open(arquivo_encontrado) as origem:
        with open(caminho_saida, "wb") as destino:
            destino.write(origem.read())

    return caminho_saida

# ==========================================
# BUSCA NOVAS VERSÕES
# ==========================================

def buscar_atualizacoes():

    ultima = descobrir_ultima_versao_local()

    if ultima is None:
        return []

    ano, mes = ultima

    atualizacoes = []

    while True:

        ano, mes = avancar_mes(ano, mes)

        agora = datetime.now()

        if (ano, mes) > (agora.year, agora.month):
            break

        if sinapi_existe(ano, mes):

            atualizacoes.append((ano, mes))

        else:
            break

    salvar_status({
        "ultima_verificacao": datetime.now().isoformat(),
        "ultima_versao_local": f"{ultima[0]}_{ultima[1]:02d}",
        "novas_versoes": [
            f"{a}_{m:02d}" for a, m in atualizacoes
        ]
    })

    return atualizacoes