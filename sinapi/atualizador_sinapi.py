from pathlib import Path
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import time
import requests
import zipfile
import io
import re
import json

try:
    from .extrair_sinapi import processar_arquivo
except ImportError:
    from extrair_sinapi import processar_arquivo

# ====== #
# PASTAS #
# ====== #

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_REFERENCIA = BASE_DIR / "sinapi/sinapi_referencia"
PASTA_PROCESSADO = BASE_DIR / "sinapi/sinapi_processado"

STATUS_FILE = BASE_DIR / "sinapi/status.json"

PASTA_REFERENCIA.mkdir(parents=True, exist_ok=True)
PASTA_PROCESSADO.mkdir(parents=True, exist_ok=True)

# ======================== #
# SESSION HTTP COM RETRIES #
# ======================== #

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
    ),
    "Accept": (
        "application/zip,application/octet-stream,"
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.caixa.gov.br/sinapi/Paginas/default.aspx",
}

# Meses anteriores ao atual a verificar no servidor da Caixa.
MESES_RETROATIVOS_BUSCA = 3

# Tentativas por mês antes de considerar indisponível naquele período.
TENTATIVAS_POR_MES = 3

# ======= #
# PADRÕES #
# ======= #

PADRAO_CSV = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.csv$"
)

PADRAO_XLSX = re.compile(
    r"(?i)SINAPI_Refer[eê]ncia_(\d{4})_(\d{2})\.xlsx$"
)

# ====== #
# STATUS
# ====== #

def salvar_status(dados):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# ============================ #
# DESCOBRE ÚLTIMA VERSÃO LOCAL #
# ============================ #

def obter_ultima_versao_local():
    versoes = []

    for arquivo in PASTA_PROCESSADO.glob("*.csv"):

        match = PADRAO_CSV.match(arquivo.name)

        if match:
            ano = int(match.group(1))
            mes = int(match.group(2))

            versoes.append((ano, mes))

    if not versoes:
        return None

    return max(versoes)

# ========== #
# AVANÇA MÊS #
# ========== #

def avancar_mes(ano, mes):

    mes += 1

    if mes > 12:
        mes = 1
        ano += 1

    return ano, mes


def retroceder_mes(ano, mes):

    mes -= 1

    if mes == 0:
        mes = 12
        ano -= 1

    return ano, mes

# ========= #
# GERAR URL #
# ========= #

def gerar_url(ano, mes):

    mes_str = f"{mes:02d}"

    return (
        f"https://www.caixa.gov.br/Downloads/"
        f"sinapi-relatorios-mensais/"
        f"SINAPI-{ano}-{mes_str}-formato-xlsx.zip"
    )

# ================ #
# TESTA EXISTÊNCIA #
# ================ #

def _resposta_indica_zip(response):
    """
    Retorna:
      True  -> arquivo ZIP confirmado
      False -> resposta definitiva de ausência (404 ou página HTML)
      None  -> inconclusivo (erro transitório, bloqueio, etc.)
    """

    status = response.status_code

    if status == 404:
        return False

    if status != 200:
        return None

    inicio = b""

    try:
        for parte in response.iter_content(1024):
            inicio = parte
            break
    finally:
        response.close()

    if inicio[:2] == b"PK":
        return True

    inicio_lower = inicio.lower()

    if (
        inicio_lower.startswith(b"<!doctype")
        or inicio_lower.startswith(b"<html")
        or b"<html" in inicio_lower
    ):
        return False

    content_type = response.headers.get("Content-Type", "").lower()

    if (
        "zip" in content_type
        or "octet-stream" in content_type
        or "spreadsheetml" in content_type
    ):
        tamanho = response.headers.get("Content-Length")

        if tamanho is not None:
            try:
                if int(tamanho) > 10_000:
                    return True
            except ValueError:
                pass

    return None


def sinapi_existe(ano, mes):
    """
    Verifica se o ZIP da SINAPI existe para o mês informado.

    Retorna True, False ou None (falha transitória de rede/servidor).
    """

    url = gerar_url(ano, mes)

    for tentativa in range(TENTATIVAS_POR_MES):

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=30,
                stream=True,
                allow_redirects=True,
            )

            resultado = _resposta_indica_zip(response)

            if resultado is not None:
                return resultado

        except requests.RequestException as e:

            print(
                f"Erro verificando "
                f"{ano}_{mes:02d} "
                f"(tentativa {tentativa + 1}): {e}"
            )

        if tentativa < TENTATIVAS_POR_MES - 1:
            time.sleep(1.5 * (tentativa + 1))

    return None


# ========================================= #
# ENCONTRA A SINAPI MAIS RECENTE DISPONÍVEL #
# ========================================= #

def encontrar_ultima_sinapi_disponivel(
    meses_retroativos=MESES_RETROATIVOS_BUSCA,
):
    """
    Procura a SINAPI mais recente nos últimos `meses_retroativos` meses.

    Retorna:
      (ano, mes) -> versão encontrada
      None       -> nenhuma versão na janela consultada
      "rede"     -> falha de rede/servidor em todos os meses verificados
    """

    agora = datetime.now()

    ano = agora.year
    mes = agora.month

    houve_falha_transitoria = False

    for _ in range(meses_retroativos):

        print(f"Verificando {ano}_{mes:02d}...")

        resultado = sinapi_existe(ano, mes)

        if resultado is True:

            print(f"Encontrada {ano}_{mes:02d}")

            return (ano, mes)

        if resultado is False:

            print(f"Não encontrada {ano}_{mes:02d}")

        else:

            houve_falha_transitoria = True
            print(
                f"Verificação inconclusiva para {ano}_{mes:02d} "
                f"(rede, bloqueio temporário ou versão não lançada)"
            )

        ano, mes = retroceder_mes(ano, mes)

    if houve_falha_transitoria:
        return "rede"

    return None

# =================== #
# BAIXA E EXTRAI XLSX #
# =================== #

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

# =================== #
# BUSCA NOVAS VERSÕES #
# =================== #

def buscar_atualizacoes():
    """
    Retorna (atualizacoes, aviso).

    aviso pode ser:
      None                 -> operação normal
      "servidor_indisponivel" -> não foi possível consultar a Caixa
      "nao_encontrada"     -> nem servidor nem pasta local têm base utilizável
    """

    ultima_local = obter_ultima_versao_local()

    ultima_disponivel = encontrar_ultima_sinapi_disponivel()

    if ultima_disponivel == "rede":

        print(
            "Não foi possível consultar a SINAPI no servidor da Caixa "
            f"(janela de {MESES_RETROATIVOS_BUSCA} meses)."
        )

        salvar_status({
            "ultima_verificacao": datetime.now().isoformat(),
            "ultima_versao_local": (
                f"{ultima_local[0]}_{ultima_local[1]:02d}"
                if ultima_local
                else None
            ),
            "novas_versoes": [],
            "erro": "servidor_indisponivel",
        })

        if ultima_local is None:
            return [], "nao_encontrada"

        return [], "servidor_indisponivel"

    if ultima_disponivel is None:

        print(
            "Nenhuma SINAPI encontrada no servidor da Caixa "
            f"nos últimos {MESES_RETROATIVOS_BUSCA} meses."
        )

        salvar_status({
            "ultima_verificacao": datetime.now().isoformat(),
            "ultima_versao_local": (
                f"{ultima_local[0]}_{ultima_local[1]:02d}"
                if ultima_local
                else None
            ),
            "novas_versoes": [],
            "erro": "nao_encontrada_servidor",
        })

        if ultima_local is None:
            return [], "nao_encontrada"

        return [], None

    # primeira execução sem CSV

    if ultima_local is None:

        print("Nenhuma versão local encontrada.")

        salvar_status({
            "ultima_verificacao": datetime.now().isoformat(),
            "ultima_versao_local": None,
            "novas_versoes": [
                f"{ultima_disponivel[0]}_{ultima_disponivel[1]:02d}"
            ]
        })

        return [ultima_disponivel], None

    # já está atualizado

    if ultima_disponivel <= ultima_local:

        print("SINAPI já está atualizada.")

        salvar_status({
            "ultima_verificacao": datetime.now().isoformat(),
            "ultima_versao_local": (
                f"{ultima_local[0]}_{ultima_local[1]:02d}"
            ),
            "novas_versoes": []
        })

        return [], None

    # existe versão nova

    salvar_status({
        "ultima_verificacao": datetime.now().isoformat(),
        "ultima_versao_local": (
            f"{ultima_local[0]}_{ultima_local[1]:02d}"
        ),
        "novas_versoes": [
            f"{ultima_disponivel[0]}_{ultima_disponivel[1]:02d}"
        ]
    })

    return [ultima_disponivel], None

# ====================== #
# REMOVE VERSÕES ANTIGAS #
# ====================== #

def limpar_versoes_antigas():

    ultima = obter_ultima_versao_local()

    if ultima is None:
        return

    ano_mais_recente, mes_mais_recente = ultima

    # -----------------------------
    # LIMPA CSVs
    # -----------------------------

    for arquivo in PASTA_PROCESSADO.glob("*.csv"):

        match = PADRAO_CSV.match(arquivo.name)

        if not match:
            continue

        ano = int(match.group(1))
        mes = int(match.group(2))

        if (ano, mes) != (ano_mais_recente, mes_mais_recente):

            try:
                arquivo.unlink()

                print(f"CSV removido: {arquivo.name}")

            except Exception as e:

                print(
                    f"Erro removendo CSV "
                    f"{arquivo.name}: {e}"
                )

    # -----------------------------
    # LIMPA XLSXs
    # -----------------------------

    for arquivo in PASTA_REFERENCIA.glob("*.xlsx"):

        match = PADRAO_XLSX.match(arquivo.name)

        if not match:
            continue

        ano = int(match.group(1))
        mes = int(match.group(2))

        if (ano, mes) != (ano_mais_recente, mes_mais_recente):

            try:
                arquivo.unlink()

                print(f"XLSX removido: {arquivo.name}")

            except Exception as e:

                print(
                    f"Erro removendo XLSX "
                    f"{arquivo.name}: {e}"
                )

if __name__ == "__main__":

    print("ARQUIVOS ENCONTRADOS:")

    for arq in PASTA_PROCESSADO.glob("*.csv"):
        print(arq.name)

    print(
        "ÚLTIMA REFERÊNCIA:",
        obter_ultima_versao_local()
    )

    atualizacoes, aviso = buscar_atualizacoes()

    print("\nAtualizações encontradas:")
    print(atualizacoes)

    if aviso:
        print(f"Aviso: {aviso}")

    for ano, mes in atualizacoes:

        try:

            caminho = baixar_e_extrair(ano, mes)

            print(f"OK: {caminho}")

            print("Iniciando processamento...")

            processar_arquivo(caminho)

            print(f"Processamento concluído: {caminho}")

            print("Removendo versões antigas...")

            limpar_versoes_antigas()

        except Exception as e:

            print(
                f"Erro ao baixar "
                f"{ano}_{mes:02d}: {e}"
            )