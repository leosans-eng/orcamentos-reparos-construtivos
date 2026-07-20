"""Modelo e cálculo de composições próprias (catálogo global do usuário)."""

import uuid
from copy import deepcopy

from core.sinapi_busca import obter_item_sinapi

TIPO_COMPONENTE_SINAPI = "sinapi"
TIPO_COMPONENTE_MERCADO = "mercado"


def _novo_id():
    return str(uuid.uuid4())


def novo_componente_sinapi(
    codigo, descricao, unidade, coeficiente, *, estado="", estado_fixado=False
):
    return {
        "id": _novo_id(),
        "tipo": TIPO_COMPONENTE_SINAPI,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "coeficiente": float(coeficiente),
        "custo_unitario": None,
        "estado": str(estado or "").strip(),
        "estado_fixado": bool(estado_fixado),
    }


def novo_componente_mercado(codigo, descricao, unidade, custo_unitario, coeficiente):
    return {
        "id": _novo_id(),
        "tipo": TIPO_COMPONENTE_MERCADO,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "coeficiente": float(coeficiente),
        "custo_unitario": float(custo_unitario),
    }


def nova_composicao(codigo, nome, unidade, componentes=None):
    return {
        "id": _novo_id(),
        "codigo": str(codigo).strip(),
        "nome": str(nome).strip(),
        "unidade": str(unidade).strip(),
        "componentes": deepcopy(componentes) if componentes else [],
    }


def estado_efetivo_componente(componente, estado_referencia="") -> str:
    """UF usada para preço/disponibilidade de um componente SINAPI."""
    if componente.get("tipo") != TIPO_COMPONENTE_SINAPI:
        return str(estado_referencia or "").strip()
    if componente.get("estado_fixado"):
        estado_item = str(componente.get("estado", "")).strip()
        if estado_item:
            return estado_item
    return str(estado_referencia or "").strip()


def componente_usa_estado_alternativo(componente, estado_referencia="") -> bool:
    if componente.get("tipo") != TIPO_COMPONENTE_SINAPI or not componente.get(
        "estado_fixado"
    ):
        return False
    estado_item = str(componente.get("estado", "")).strip()
    estado_ref = str(estado_referencia or "").strip()
    return bool(estado_item) and estado_item != estado_ref


def definir_estado_componente_sinapi(
    componente, estado, sinapi, *, estado_referencia="", fixar=None
):
    """Define a UF de preço de um componente SINAPI da composição."""
    if componente.get("tipo") != TIPO_COMPONENTE_SINAPI:
        raise ValueError("Apenas componentes SINAPI possuem estado próprio.")
    estado = str(estado or "").strip()
    if not estado:
        raise ValueError("Informe o estado.")
    linha = obter_item_sinapi(sinapi, componente.get("codigo", ""), estado)
    if linha is None:
        raise ValueError(
            f"Código {componente.get('codigo', '')} não encontrado para o estado {estado}."
        )
    descricao = str(linha.get("descricao", "")).strip()
    if descricao:
        componente["descricao"] = descricao
    unidade = str(linha.get("unidade", "")).strip()
    if unidade:
        componente["unidade"] = unidade
    componente["estado"] = estado
    if fixar is None:
        fixar = estado != str(estado_referencia or "").strip()
    componente["estado_fixado"] = bool(fixar)
    return componente


def obter_composicao_por_id(catalogo, composicao_id):
    for comp in catalogo:
        if comp.get("id") == composicao_id:
            return comp
    return None


def filtrar_composicoes_catalogo(catalogo, consulta="", unidade=None):
    """Filtra composições do catálogo por texto (código/nome) e unidade."""
    texto = str(consulta or "").strip().lower()
    alvo_un = str(unidade or "").strip().upper() if unidade else ""
    filtradas = []
    for comp in catalogo:
        codigo = str(comp.get("codigo", "")).lower()
        nome = str(comp.get("nome", "")).lower()
        if texto and texto not in codigo and texto not in nome:
            continue
        if alvo_un:
            un = str(comp.get("unidade", "")).strip().upper()
            if un != alvo_un:
                continue
        filtradas.append(comp)
    return filtradas


def calcular_custo_unitario(composicao, sinapi_df, estado):
    """Retorna (custo_unitario, tem_depreciado)."""
    if not composicao:
        return 0.0, True

    custo = 0.0
    tem_depreciado = False
    estado = str(estado or "").strip()

    for componente in composicao.get("componentes", []):
        tipo = componente.get("tipo")
        coeficiente = float(componente.get("coeficiente", 0))

        if tipo == TIPO_COMPONENTE_MERCADO:
            try:
                unitario = float(componente.get("custo_unitario", 0))
            except (TypeError, ValueError):
                unitario = 0.0
            custo += unitario * coeficiente
        elif tipo == TIPO_COMPONENTE_SINAPI:
            estado_comp = estado_efetivo_componente(componente, estado)
            if not estado_comp:
                tem_depreciado = True
                continue
            linha = obter_item_sinapi(
                sinapi_df, componente.get("codigo", ""), estado_comp
            )
            if linha is None:
                tem_depreciado = True
                continue
            try:
                unitario = float(linha.get("custo", 0))
            except (TypeError, ValueError):
                unitario = 0.0
            custo += unitario * coeficiente

    return custo, tem_depreciado


def verificar_componentes_depreciados(composicao, sinapi_df, estado):
    """Lista ids de componentes SINAPI ausentes na UF efetiva."""
    if not composicao:
        return []

    depreciados = []
    estado = str(estado or "").strip()
    for componente in composicao.get("componentes", []):
        if componente.get("tipo") != TIPO_COMPONENTE_SINAPI:
            continue
        estado_comp = estado_efetivo_componente(componente, estado)
        if not estado_comp:
            depreciados.append(componente.get("id"))
            continue
        linha = obter_item_sinapi(
            sinapi_df, componente.get("codigo", ""), estado_comp
        )
        if linha is None:
            depreciados.append(componente.get("id"))
    return depreciados


def custo_composicao_propria_item(item, catalogo, sinapi, estado):
    """
    Custo unitário de um item de orçamento que referencia o catálogo.
    Retorna (custo_unitario, tem_depreciado).
    """
    composicao = obter_composicao_por_id(catalogo, item.get("composicao_catalogo_id"))
    if composicao is None:
        referencia = item.get("custo_unitario_referencia")
        if referencia is not None:
            try:
                return float(referencia), True
            except (TypeError, ValueError):
                pass
        return 0.0, True
    estado_calc = str(estado or "").strip()
    if item.get("estado_fixado"):
        estado_item = str(item.get("estado", "")).strip()
        if estado_item:
            estado_calc = estado_item
    return calcular_custo_unitario(composicao, sinapi, estado_calc)
