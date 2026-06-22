import re
import unicodedata

import pandas as pd

# Sinônimos usados na busca (chave e variantes já normalizadas sem acento).
# Se o usuário digitar qualquer termo do grupo, os demais também contam na busca.
SINONIMOS = {
    "ceramica": ["ceramico", "ceramica", "ceramicos", "porcelanato", "revestimento ceramico"],
    "azulejo": ["azulejo", "azulejos", "pastilha", "pastilhas"],
    "reboco": ["reboco", "rebocos", "emboco", "emboço", "argamassa de reboco"],
    "chapisco": ["chapisco", "chapiscos", "emboço", "emboco"],
    "pintura": ["pintura", "pinturas", "tinta", "pintar", "latex", "látex"],
    "alvenaria": ["alvenaria", "alvenarias", "tijolo", "tijolos", "bloco", "blocos"],
    "concreto": ["concreto", "concretagem", "cimento", "forma"],
    "piso": ["piso", "pisos", "piso ceramico", "assoalho", "lajota"],
    "laje": ["laje", "lajes", "lajota"],
    "impermeabilizacao": ["impermeabilizacao", "impermeabilização", "manta", "mantas", "vedacao", "vedação"],
    "rodape": ["rodape", "rodapé", "rodapes", "soleira"],
    "esquadria": ["esquadria", "esquadrias", "janela", "janelas", "porta", "portas"],
    "gesso": ["gesso", "drywall", "placa de gesso", "forro"],
    "eletrica": ["eletrica", "elétrica", "eletroduto", "fiacao", "fiação", "tomada"],
    "hidraulica": ["hidraulica", "hidráulica", "tubo", "tubos", "agua", "água", "esgoto"],
    "demolicao": ["demolicao", "demolição", "demolir", "remocao", "remoção"],
    "limpeza": ["limpeza", "limpar", "lavagem"],
    "telhado": ["telhado", "telha", "telhas", "cobertura", "coberturas"],
    "trinca": ["trinca", "trincas", "fissura", "fissuras", "rachadura"],
    "reparo": ["reparo", "reparos", "conserto", "restauracao", "restauração"],
}

STOPWORDS = {
    "de", "da", "do", "das", "dos", "para", "com", "em", "a", "o", "e",
    "um", "uma", "ao", "na", "no", "nas", "nos", "por", "ate", "até",
}


def normalizar_texto(texto):
    if texto is None:
        return ""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def tokenizar_consulta(consulta):
    norm = normalizar_texto(consulta)
    tokens = re.findall(r"[a-z0-9]+", norm)
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def expandir_token(token):
    grupo = {token}
    for chave, variantes in SINONIMOS.items():
        conjunto = {normalizar_texto(chave)}
        conjunto.update(normalizar_texto(v) for v in variantes)
        if token in conjunto:
            grupo |= conjunto
    return grupo


def _consulta_parece_codigo(consulta):
    limpo = re.sub(r"[\s.]", "", consulta.strip())
    return bool(limpo) and limpo.isdigit()


def _filtrar_por_estado(sinapi, estado):
    if sinapi.empty or "estado" not in sinapi.columns:
        return sinapi.iloc[0:0].copy()
    estado = str(estado).strip()
    if not estado:
        return sinapi.iloc[0:0].copy()
    return sinapi[sinapi["estado"].astype(str).str.strip() == estado].copy()


def _mascara_grupos(descricoes_norm, grupos):
    mascara = pd.Series(True, index=descricoes_norm.index)
    for grupo in grupos:
        grupo_mask = pd.Series(False, index=descricoes_norm.index)
        for termo in grupo:
            grupo_mask |= descricoes_norm.str.contains(termo, regex=False, na=False)
        mascara &= grupo_mask
    return mascara


def _pontuar_linha(codigo, descricao, grupos, consulta_norm):
    score = 0
    codigo_norm = normalizar_texto(codigo).replace(".", "")
    consulta_codigo = re.sub(r"[\s.]", "", consulta_norm)

    if consulta_codigo and consulta_codigo == codigo_norm:
        score += 1000
    elif consulta_codigo and consulta_codigo in codigo_norm:
        score += 500

    desc_norm = normalizar_texto(descricao)
    for grupo in grupos:
        for termo in grupo:
            if termo in desc_norm:
                score += 10 + len(termo)
                break
    return score


def obter_unidades_sinapi(sinapi, estado=None):
    """Unidades distintas na base, opcionalmente restritas a um estado."""
    if sinapi.empty or "unidade" not in sinapi.columns:
        return []
    df = _filtrar_por_estado(sinapi, estado) if estado else sinapi
    if df.empty:
        return []
    unidades = df["unidade"].dropna().astype(str).str.strip().unique()
    return sorted(u for u in unidades if u)


def _filtrar_por_unidade(df, unidade):
    if df.empty or not unidade or unidade == "Todas":
        return df
    if "unidade" not in df.columns:
        return df
    alvo = str(unidade).strip().upper()
    return df[df["unidade"].astype(str).str.strip().str.upper() == alvo].copy()


def buscar_sinapi(sinapi, estado, consulta, limite=250, modo_parcial=False, unidade=None):
    """
    Busca insumos ou composições SINAPI no DataFrame carregado.

    Retorna (DataFrame resultados, mensagem_status).
    Pensado para reutilização futura em módulo de composições próprias.
    """
    colunas = list(sinapi.columns) if not sinapi.empty else [
        "codigo", "descricao", "unidade", "estado", "custo",
    ]
    vazio = pd.DataFrame(columns=colunas)

    df = _filtrar_por_estado(sinapi, estado)
    if df.empty:
        return vazio, "Nenhum item para o estado selecionado."

    texto = consulta.strip()
    if not texto:
        return vazio, "Digite palavras ou o código do insumo ou composição para pesquisar."

    if _consulta_parece_codigo(texto):
        codigo_busca = re.sub(r"\s", "", texto)
        mask = df["codigo"].astype(str).str.replace(".", "", regex=False).str.contains(
            codigo_busca, regex=False, na=False
        )
        resultados = _filtrar_por_unidade(df[mask].copy(), unidade)
        if resultados.empty:
            sufixo_un = f" na unidade {unidade}" if unidade and unidade != "Todas" else ""
            return vazio, f"Nenhum insumo ou composição com código contendo “{texto}”{sufixo_un}."
        return resultados.head(limite), f"{len(resultados.head(limite))} insumo(s) ou composição(ões) encontrado(s)."

    tokens = tokenizar_consulta(texto)
    if not tokens:
        return vazio, "Use ao menos uma palavra com 2 ou mais letras."

    grupos = [expandir_token(t) for t in tokens]
    descricoes_norm = df["descricao"].astype(str).map(normalizar_texto)

    mascara = _mascara_grupos(descricoes_norm, grupos)
    resultados = df[mascara].copy()
    mensagem_parcial = ""

    if resultados.empty and not modo_parcial:
        # Fallback: qualquer token (ou sinônimo) — resultado parcial
        mascara_parcial = pd.Series(False, index=descricoes_norm.index)
        for grupo in grupos:
            for termo in grupo:
                mascara_parcial |= descricoes_norm.str.contains(termo, regex=False, na=False)
        resultados = df[mascara_parcial].copy()
        if not resultados.empty:
            mensagem_parcial = " (correspondência parcial — nem todas as palavras)"

    if resultados.empty:
        return vazio, "Nenhum insumo ou composição encontrada. Tente sinônimos ou menos palavras."

    consulta_norm = normalizar_texto(texto)
    resultados["_score"] = [
        _pontuar_linha(row["codigo"], row["descricao"], grupos, consulta_norm)
        for _, row in resultados.iterrows()
    ]
    resultados = resultados.sort_values("_score", ascending=False).drop(columns=["_score"])
    resultados = _filtrar_por_unidade(resultados, unidade)
    if resultados.empty:
        sufixo_un = f" na unidade {unidade}" if unidade and unidade != "Todas" else ""
        return vazio, f"Nenhum insumo ou composição encontrada{sufixo_un}. Tente sinônimos ou menos palavras."

    total = len(resultados)
    exibidos = resultados.head(limite)

    msg = f"{len(exibidos)} de {total} insumo(s) ou composição(ões) encontrada(s){mensagem_parcial}."
    if total > limite:
        msg += f" Exibindo as {limite} mais relevantes."

    return exibidos, msg


def obter_item_sinapi(sinapi, codigo, estado):
    """Retorna uma linha da base ou None — útil para composições futuras."""
    if sinapi.empty:
        return None
    codigo = str(codigo).strip()
    estado = str(estado).strip()
    linhas = sinapi[
        (sinapi["codigo"].astype(str).str.strip() == codigo)
        & (sinapi["estado"].astype(str).str.strip() == estado)
    ]
    if linhas.empty:
        return None
    return linhas.iloc[0]
