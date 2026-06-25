"""Modelo e cálculo de composições próprias (catálogo global do usuário)."""

import uuid
from copy import deepcopy

from core.sinapi_busca import obter_item_sinapi

TIPO_COMPONENTE_SINAPI = "sinapi"
TIPO_COMPONENTE_MERCADO = "mercado"


def _novo_id():
    return str(uuid.uuid4())


def novo_componente_sinapi(codigo, descricao, unidade, coeficiente):
    return {
        "id": _novo_id(),
        "tipo": TIPO_COMPONENTE_SINAPI,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "coeficiente": float(coeficiente),
        "custo_unitario": None,
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


def obter_composicao_por_id(catalogo, composicao_id):
    for comp in catalogo:
        if comp.get("id") == composicao_id:
            return comp
    return None


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
            if not estado:
                tem_depreciado = True
                continue
            linha = obter_item_sinapi(sinapi_df, componente.get("codigo", ""), estado)
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
    """Lista ids de componentes SINAPI ausentes na base para o estado."""
    if not composicao or not estado:
        return []

    depreciados = []
    estado = str(estado).strip()
    for componente in composicao.get("componentes", []):
        if componente.get("tipo") != TIPO_COMPONENTE_SINAPI:
            continue
        linha = obter_item_sinapi(sinapi_df, componente.get("codigo", ""), estado)
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
        return 0.0, True
    return calcular_custo_unitario(composicao, sinapi, estado)
