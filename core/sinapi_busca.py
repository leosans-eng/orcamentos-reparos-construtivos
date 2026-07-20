import re
import unicodedata

import pandas as pd

from core.sinapi_base import COLUNAS_BUSCA, SinapiBase

# Sinônimos usados na busca (chave e variantes já normalizadas sem acento).
# Se o usuário digitar qualquer termo do grupo, os demais também contam na busca.
SINONIMOS = {
    "ceramica": ["ceramico", "ceramica", "ceramicos", "porcelanato", "revestimento ceramico"],
    "azulejo": ["azulejo", "azulejos", "pastilha", "pastilhas"],
    "reboco": ["reboco", "rebocos", "emboco", "emboço", "argamassa de reboco", "reboque"],
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

TIPO_TODOS = "Todos"
TIPO_INSUMO = "Insumo"
TIPO_COMPOSICAO = "Composição"
VALORES_FILTRO_TIPO = (TIPO_TODOS, TIPO_INSUMO, TIPO_COMPOSICAO)


def nome_tipo_sinapi(valor) -> str:
    letra = str(valor or "").strip().upper()[:1]
    if letra == "I":
        return TIPO_INSUMO
    if letra == "C":
        return TIPO_COMPOSICAO
    if letra == "P":
        return "Composição própria"
    return ""


def tipo_sinapi_para_filtro(selecao) -> str | None:
    texto = str(selecao or "").strip()
    if texto == TIPO_INSUMO:
        return "I"
    if texto == TIPO_COMPOSICAO:
        return "C"
    return None


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


def _as_base(sinapi: SinapiBase) -> SinapiBase:
    return sinapi


def _filtrar_por_estado(sinapi, estado):
    base = _as_base(sinapi)
    return base.dataframe_estado(estado)


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


def _unidades_do_dataframe(df):
    if df.empty or "unidade" not in df.columns:
        return []
    unidades = df["unidade"].dropna().astype(str).str.strip().unique()
    return sorted(u for u in unidades if u)


def _filtrar_por_consulta(df, consulta, permitir_parcial=True):
    """
    Filtra um DataFrame já restrito ao estado.
    Retorna (resultados, busca_parcial).
    """
    texto = consulta.strip()
    if not texto:
        return df.iloc[0:0].copy(), False

    if _consulta_parece_codigo(texto):
        codigo_busca = re.sub(r"\s", "", texto)
        mask = df["codigo"].astype(str).str.replace(".", "", regex=False).str.contains(
            codigo_busca, regex=False, na=False
        )
        return df[mask].copy(), False

    tokens = tokenizar_consulta(texto)
    if not tokens:
        return df.iloc[0:0].copy(), False

    grupos = [expandir_token(t) for t in tokens]
    descricoes_norm = df["descricao"].astype(str).map(normalizar_texto)

    mascara = _mascara_grupos(descricoes_norm, grupos)
    resultados = df[mascara].copy()
    parcial = False

    if resultados.empty and permitir_parcial:
        mascara_parcial = pd.Series(False, index=descricoes_norm.index)
        for grupo in grupos:
            for termo in grupo:
                mascara_parcial |= descricoes_norm.str.contains(termo, regex=False, na=False)
        resultados = df[mascara_parcial].copy()
        parcial = not resultados.empty

    return resultados, parcial


def obter_unidades_sinapi(sinapi, estado=None, consulta=None):
    """Unidades distintas na base, opcionalmente restritas ao estado e à consulta."""
    base = _as_base(sinapi)
    if base.empty:
        return []
    df = base.dataframe_estado(estado) if estado else base.catalogo
    if df.empty:
        return []
    if consulta and consulta.strip():
        df, _ = _filtrar_por_consulta(df, consulta)
    return _unidades_do_dataframe(df)


def _filtrar_por_unidade(df, unidade):
    if df.empty or not unidade or unidade == "Todas":
        return df
    if "unidade" not in df.columns:
        return df
    alvo = str(unidade).strip().upper()
    return df[df["unidade"].astype(str).str.strip().str.upper() == alvo].copy()


def _filtrar_por_tipo(df, tipo):
    if df.empty or not tipo or "tipo" not in df.columns:
        return df
    alvo = str(tipo).strip().upper()[:1]
    return df[df["tipo"].astype(str).str.strip().str.upper().str[:1] == alvo].copy()


def pesquisar_sinapi(sinapi, estado, consulta, unidade=None, tipo=None, limite=250):
    """
    Busca insumos/composições em uma única passagem de filtro.
    Retorna (resultados, mensagem, unidades_disponiveis).
    """
    colunas = list(COLUNAS_BUSCA)
    vazio = pd.DataFrame(columns=colunas)

    df = _filtrar_por_estado(sinapi, estado)
    if df.empty:
        return vazio, "Nenhum item para o estado selecionado.", []

    texto = consulta.strip()
    if not texto:
        return vazio, "Digite palavras ou o código do insumo ou composição para pesquisar.", _unidades_do_dataframe(df)

    tokens = tokenizar_consulta(texto)
    if not _consulta_parece_codigo(texto) and not tokens:
        return vazio, "Use ao menos uma palavra com 2 ou mais letras.", _unidades_do_dataframe(df)

    resultados, parcial = _filtrar_por_consulta(df, texto)
    unidades = _unidades_do_dataframe(resultados)

    if resultados.empty:
        return vazio, "Nenhum insumo ou composição encontrada. Tente sinônimos ou menos palavras.", unidades

    if not _consulta_parece_codigo(texto):
        consulta_norm = normalizar_texto(texto)
        grupos = [expandir_token(t) for t in tokens]
        resultados = resultados.copy()
        resultados["_score"] = resultados.apply(
            lambda row: _pontuar_linha(row["codigo"], row["descricao"], grupos, consulta_norm),
            axis=1,
        )
        resultados = pd.DataFrame(resultados).sort_values(by="_score", ascending=False)
        resultados = resultados.drop(columns=["_score"])

    resultados = _filtrar_por_tipo(resultados, tipo)
    if not isinstance(resultados, pd.DataFrame) or resultados.empty:
        sufixo_tipo = ""
        if tipo == "I":
            sufixo_tipo = " do tipo Insumo"
        elif tipo == "C":
            sufixo_tipo = " do tipo Composição"
        return (
            vazio,
            f"Nenhum insumo ou composição encontrada{sufixo_tipo}. "
            "Tente sinônimos ou menos palavras.",
            unidades,
        )

    resultados = _filtrar_por_unidade(resultados, unidade)
    if not isinstance(resultados, pd.DataFrame) or resultados.empty:
        sufixo_un = f" na unidade {unidade}" if unidade and unidade != "Todas" else ""
        return vazio, f"Nenhum insumo ou composição encontrada{sufixo_un}. Tente sinônimos ou menos palavras.", unidades

    total = len(resultados)
    exibidos = resultados.head(limite)
    sufixo_parcial = " (correspondência parcial — nem todas as palavras)" if parcial else ""
    msg = f"{len(exibidos)} de {total} insumo(s) ou composição(ões) encontrada(s){sufixo_parcial}."
    if total > limite:
        msg += f" Exibindo as {limite} mais relevantes."

    return exibidos, msg, unidades


def buscar_sinapi(sinapi, estado, consulta, limite=250, modo_parcial=False, unidade=None, tipo=None):
    """
    Busca insumos ou composições SINAPI no DataFrame carregado.

    Retorna (DataFrame resultados, mensagem_status).
    Pensado para reutilização futura em módulo de composições próprias.
    """
    resultados, mensagem, _unidades = pesquisar_sinapi(
        sinapi,
        estado,
        consulta,
        unidade=unidade,
        tipo=tipo,
        limite=limite,
    )
    return resultados, mensagem


def obter_item_sinapi(sinapi, codigo, estado):
    """Retorna uma linha da base ou None."""
    base = _as_base(sinapi)
    if base.empty:
        return None
    return base.obter_linha(codigo, estado)


def estados_com_codigo(sinapi, codigo) -> list[str]:
    """UFs em que o código SINAPI possui preço na base carregada."""
    base = _as_base(sinapi)
    codigo = str(codigo or "").strip()
    if base.empty or not codigo:
        return []
    precos = base.precos
    if precos.empty:
        return []
    mask = precos["codigo"].astype(str).str.strip() == codigo
    if not mask.any():
        return []
    return sorted(
        precos.loc[mask, "estado"].dropna().astype(str).str.strip().unique().tolist()
    )


def item_sinapi_ausente(sinapi, codigo, estado) -> bool:
    """True quando o código não existe na base SINAPI para o estado selecionado."""
    if not str(estado or "").strip():
        return False
    return obter_item_sinapi(sinapi, codigo, estado) is None
