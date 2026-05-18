from openpyxl import load_workbook
from pathlib import Path
import csv
import sys
import os

# ---------------------------- #
# PASTAS                       #
# ---------------------------- #

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_REFERENCIA = BASE_DIR / "sinapi/sinapi_referencia"
PASTA_PROCESSADO = BASE_DIR / "sinapi/sinapi_processado"

PASTA_PROCESSADO.mkdir(parents=True, exist_ok=True)

# ---------------------------- #
# PROCESSAR UM ARQUIVO         #
# ---------------------------- #

def processar_arquivo(caminho_excel, callback=None):

    caminho_excel = Path(caminho_excel)

    nome_csv = caminho_excel.stem + ".csv"

    caminho_csv = os.path.join(
        PASTA_PROCESSADO,
        nome_csv
    )

    def log(msg):
        print(msg)

        if callback:
            callback(msg)

    log("\n=================================")
    log(f"Processando: {caminho_excel.name}")

    if not caminho_excel.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho_excel}"
        )

    wb = load_workbook(
        caminho_excel,
        read_only=True,
        data_only=True
    )

    # ========================================================== #
    # EXTRAÇÃO DAS COMPOSIÇÕES (CSD)                             #
    # ========================================================== #

    ws = wb["CSD"]

    estados = []
    colunas_custo = []

    col = 5  # coluna E

    while True:

        estado = ws.cell(row=9, column=col).value

        if not estado:
            break

        estados.append(str(estado).strip())
        colunas_custo.append(col)

        col += 2

        if col > 200:
            break

    log(f"Estados detectados ({len(estados)}): {estados}")

    # ---------------------------- #
    # LER CÓDIGOS DA ABA ANALÍTICO #
    # ---------------------------- #

    log("Lendo códigos da aba Analítico...")

    ws_analitico = wb["Analítico"]

    mapa_codigos = {}

    for row in ws_analitico.iter_rows(min_row=11, values_only=True):

        tipo = row[2]
        codigo = row[1]
        descricao = row[4]
        unidade = row[5]

        if (
            tipo is None
            and isinstance(codigo, (int, float))
            and isinstance(descricao, str)
            and isinstance(unidade, str)
        ):
            chave = (descricao.strip(), unidade.strip())
            mapa_codigos[chave] = int(codigo)

    log(f"Códigos carregados: {len(mapa_codigos)} | Extraindo composições da aba CSD...")

    contador = 0
    linhas_gravadas = 0

    with open(
        caminho_csv,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "codigo",
            "descricao",
            "unidade",
            "estado",
            "custo"
        ])

        indices_custo = [c-1 for c in colunas_custo]

        # ---------------------------- #
        # EXTRAÇÃO CSD                 #
        # ---------------------------- #

        for row in ws.iter_rows(min_row=11, values_only=True):

            contador += 1

            descricao = row[2]
            unidade = row[3]

            if not isinstance(descricao, str):
                continue

            chave = (descricao.strip(), unidade.strip())
            codigo = mapa_codigos.get(chave)

            if not codigo:
                continue

            for estado, idx in zip(estados, indices_custo):

                custo = row[idx]

                if custo is None:
                    continue

                writer.writerow([
                    codigo,
                    descricao,
                    unidade,
                    estado,
                    float(custo)
                ])

                linhas_gravadas += 1

            if contador % 1000 == 0:

                log(
                    f"CSD: {contador} linhas analisadas | "
                    f"{linhas_gravadas} registros gravados"
                )

        log("==========Extração das composições finalizada.==========")

        # ========================================================== #
        # EXTRAÇÃO DOS INSUMOS (ISD)                                 #
        # ========================================================== #

        log("\nExtraindo insumos da aba ISD...")

        ws_isd = wb["ISD"]

        # localizar cabeçalho

        linha_cabecalho = None

        for r in range(1, 50):

            valor = ws_isd.cell(row=r, column=2).value

            if valor and "Código" in str(valor):
                linha_cabecalho = r
                break

        if not linha_cabecalho:
            raise Exception("Cabeçalho da ISD não encontrado")

        log(f"Cabeçalho ISD encontrado na linha: {linha_cabecalho}")

        estados_isd = []
        colunas_custo_isd = []

        col = 6  # coluna F

        while True:

            estado = ws_isd.cell(row=linha_cabecalho, column=col).value

            if not estado:
                break

            estados_isd.append(str(estado).strip())
            colunas_custo_isd.append(col - 1)

            col += 1

            if col > 200:
                break

        log(f"Estados detectados ({len(estados_isd)}): {estados_isd}")

        linhas_isd = 0

        for row in ws_isd.iter_rows(
            min_row=linha_cabecalho + 1,
            values_only=True
        ):

            linhas_isd += 1

            codigo = row[1]
            descricao = row[2]
            unidade = row[3]

            if not codigo:
                continue

            if not isinstance(descricao, str):
                continue

            for estado, idx in zip(estados_isd, colunas_custo_isd):

                custo = row[idx]

                if custo is None:
                    continue

                writer.writerow([
                    int(codigo),
                    descricao,
                    unidade,
                    estado,
                    float(custo)
                ])

                linhas_gravadas += 1

            if linhas_isd % 2000 == 0:

                log(
                    f"ISD: {linhas_isd} linhas analisadas | "
                    f"{linhas_gravadas} registros gravados"
                )

    log(f"Arquivo CSV criado: {caminho_csv}")
    log(f"Linhas CSD analisadas: {contador}")
    log(f"Linhas ISD analisadas: {linhas_isd}")
    log(f"Registros totais: {linhas_gravadas}")

    log("\n==========Extração finalizada.==========")

    return caminho_csv

# ==========================================
# EXECUÇÃO DIRETA
# ==========================================

if __name__ == "__main__":

    arquivos_excel = [
        f for f in PASTA_REFERENCIA.glob("*.xlsx")
        if not f.name.startswith("~$")
    ]

    print("Arquivos encontrados:")

    for arquivo in arquivos_excel:
        print("-", arquivo.name)

    for arquivo in arquivos_excel:

        processar_arquivo(arquivo)

    print("\n==========Script concluído.==========")