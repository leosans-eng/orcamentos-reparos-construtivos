from pathlib import Path
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import requests
import zipfile
import io
import re
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
# SESSION HTTP COM RETRIES
# ==========================================

session = requests.Session()

retry = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"]
)

adapter = HTTPAdapter(max_retries=retry)

session.mount("https://", adapter)
session.mount("http://", adapter)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

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

def obter_ultima_versao_local():
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

    for tentativa in range(3):

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=20,
                stream=True,
                allow_redirects=True
            )

            if response.status_code == 200:

                content_type = response.headers.get(
                    "Content-Type",
                    ""
                ).lower()

                if (
                    "zip" in content_type
                    or "octet-stream" in content_type
                ):
                    return True

            return False

        except requests.RequestException as e:

            print(
                f"Erro verificando "
                f"{ano}_{mes:02d} "
                f"(tentativa {tentativa + 1}): {e}"
            )

    return False

# ==========================================
# BAIXA E EXTRAI XLSX
# ==========================================

def baixar_e_extrair(ano, mes):

    url = gerar_url(ano, mes)

    mes_str = f"{mes:02d}"

    nome_xlsx = f"SINAPI_Referência_{ano}_{mes_str}.xlsx"

    print(f"Baixando {nome_xlsx}...")

    response = session.get(
        url,
        headers=HEADERS,
        timeout=120
    )

    response.raise_for_status()

    zip_file = zipfile.ZipFile(
        io.BytesIO(response.content)
    )

    arquivo_encontrado = None

    for nome in zip_file.namelist():

        nome_limpo = Path(nome).name

        if nome_limpo.lower() == nome_xlsx.lower():

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

    print(f"Extraído: {nome_xlsx}")

    return caminho_saida

# ==========================================
# BUSCA NOVAS VERSÕES
# ==========================================

def buscar_atualizacoes():

    ultima = obter_ultima_versao_local()

    if ultima is None:
        return []

    ano, mes = ultima

    atualizacoes = []

    agora = datetime.now()

    ano_atual = agora.year
    mes_atual = agora.month

    while True:

        ano, mes = avancar_mes(ano, mes)

        if (ano, mes) > (ano_atual, mes_atual):
            break

        print(f"Verificando {ano}_{mes:02d}...")

        if sinapi_existe(ano, mes):

            print(f"Encontrada {ano}_{mes:02d}")

            atualizacoes.append((ano, mes))

        else:

            print(f"Não encontrada {ano}_{mes:02d}")

    salvar_status({
        "ultima_verificacao": datetime.now().isoformat(),
        "ultima_versao_local": f"{ultima[0]}_{ultima[1]:02d}",
        "novas_versoes": [
            f"{a}_{m:02d}" for a, m in atualizacoes
        ]
    })

    return atualizacoes
    
if __name__ == "__main__":

    print("ARQUIVOS ENCONTRADOS:")

    for arq in PASTA_PROCESSADO.glob("*.csv"):
        print(arq.name)

    print(
        "ÚLTIMA REFERÊNCIA:",
        obter_ultima_versao_local()
    )

    atualizacoes = buscar_atualizacoes()

    print("\nAtualizações encontradas:")
    print(atualizacoes)

    for ano, mes in atualizacoes:

        try:

            caminho = baixar_e_extrair(ano, mes)

            print(f"OK: {caminho}")

        except Exception as e:

            print(
                f"Erro ao baixar "
                f"{ano}_{mes:02d}: {e}"
            )