from openpyxl import load_workbook
import os
import csv

# ---------------------------- #
# PASTAS                       #
# ---------------------------- #

pasta_script = os.path.dirname(__file__)

pasta_excel = os.path.join(
    pasta_script,
    "sinapi_referencia"
)

pasta_saida = os.path.join(
    pasta_script,
    "sinapi_processado"
)

os.makedirs(pasta_saida, exist_ok=True)

# ---------------------------- #
# LISTAR EXCELS                #
# ---------------------------- #

arquivos_excel = [
    f for f in os.listdir(pasta_excel)
    if f.lower().endswith(".xlsx") and not f.startswith("~$")
]

print("Arquivos encontrados:")
for a in arquivos_excel:
    print("-", a)

# ---------------------------- #
# PROCESSAR CADA EXCEL         #
# ---------------------------- #

for arquivo in arquivos_excel:

    caminho_excel = os.path.join(pasta_excel, arquivo)
    nome_csv = os.path.splitext(arquivo)[0] + ".csv"
    caminho_csv = os.path.join(pasta_saida, nome_csv)

    print("\n=================================")
    print("Processando:", arquivo)

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

    print(f"Estados detectados ({len(estados)}): {estados}")

    # ---------------------------- #
    # LER CÓDIGOS DA ABA ANALÍTICO #
    # ---------------------------- #

    print("Lendo códigos da aba Analítico...")

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

    print("Códigos carregados:", len(mapa_codigos), "| Extraindo composições da aba CSD...")

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

                print(
                    f"CSD: {contador} linhas analisadas | "
                    f"{linhas_gravadas} registros gravados"
                )

        print("==========Extração das composições finalizada.==========")

        # ========================================================== #
        # EXTRAÇÃO DOS INSUMOS (ISD)                                 #
        # ========================================================== #

        print("\nExtraindo insumos da aba ISD...")

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

        print("Cabeçalho ISD encontrado na linha:", linha_cabecalho)

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

        print(f"Estados detectados ({len(estados_isd)}): {estados_isd}")

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

                print(
                    f"ISD: {linhas_isd} linhas analisadas | "
                    f"{linhas_gravadas} registros gravados"
                )

    print("Arquivo CSV criado:", nome_csv)
    print("Linhas CSD analisadas:", contador)
    print("Linhas ISD analisadas:", linhas_isd)
    print("Registros totais:", linhas_gravadas)

print("\n==========Extração finalizada.==========")