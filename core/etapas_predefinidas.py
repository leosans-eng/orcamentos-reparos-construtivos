"""Modelo e aplicação de etapas pré-definidas no orçamento customizado."""

from __future__ import annotations

import uuid
from copy import deepcopy

from core.composicoes_proprias import obter_composicao_por_id
from core.composicoes_proprias_storage import obter_por_codigo
from core.sinapi_busca import obter_item_sinapi

TIPO_ITEM_SINAPI = "sinapi"
TIPO_ITEM_PROPRIA = "propria"

QUANTIDADE_PADRAO_ETAPA = 1.0


def _novo_id() -> str:
    return str(uuid.uuid4())


def nova_etapa_predefinida(nome: str) -> dict:
    return {
        "id": _novo_id(),
        "nome": str(nome).strip(),
        "itens": [],
    }


def novo_item_sinapi_template(
    codigo: str,
    descricao: str,
    unidade: str,
    tipo_sinapi: str = "",
) -> dict:
    return {
        "id": _novo_id(),
        "tipo": TIPO_ITEM_SINAPI,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "tipo_sinapi": str(tipo_sinapi or "").strip().upper()[:1],
    }


def novo_item_propria_template(
    composicao_catalogo_id: str,
    codigo: str,
    nome: str,
    unidade: str,
) -> dict:
    return {
        "id": _novo_id(),
        "tipo": TIPO_ITEM_PROPRIA,
        "composicao_catalogo_id": str(composicao_catalogo_id or "").strip(),
        "codigo": str(codigo).strip(),
        "nome": str(nome).strip(),
        "unidade": str(unidade).strip(),
    }


def aplicar_etapa_no_orcamento(
    orcamento,
    etapa: dict,
    sinapi,
    estado: str,
    catalogo,
    *,
    quantidade: float = QUANTIDADE_PADRAO_ETAPA,
    nome_override: str | None = None,
) -> tuple[str, list[str]]:
    """Cria grupo e itens do modelo no orçamento. Retorna (grupo_id, avisos)."""
    nome = (nome_override if nome_override is not None else etapa.get("nome", "")).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")

    grupo_id = orcamento.adicionar_grupo(nome)
    avisos: list[str] = []
    estado = str(estado or "").strip()
    dados_catalogo = {"composicoes": catalogo} if catalogo is not None else None

    for ref in etapa.get("itens", []):
        tipo = ref.get("tipo")
        if tipo == TIPO_ITEM_SINAPI:
            codigo = str(ref.get("codigo", "")).strip()
            descricao = str(ref.get("descricao", "")).strip()
            unidade = str(ref.get("unidade", "")).strip()
            tipo_sinapi = str(ref.get("tipo_sinapi", "")).strip().upper()[:1]

            custo = 0.0
            if estado:
                linha = obter_item_sinapi(sinapi, codigo, estado)
                if linha is not None:
                    try:
                        custo = float(linha.get("custo", 0))
                    except (TypeError, ValueError):
                        custo = 0.0
                    if not descricao:
                        descricao = str(linha.get("descricao", "")).strip()
                    if not unidade:
                        unidade = str(linha.get("unidade", "")).strip()
                    if not tipo_sinapi:
                        tipo_ic = str(linha.get("tipo", "")).strip().upper()[:1]
                        if tipo_ic in ("I", "C"):
                            tipo_sinapi = tipo_ic
                else:
                    avisos.append(
                        f"SINAPI {codigo} não encontrado na base para {estado}; "
                        "item adicionado com custo zero."
                    )
            else:
                avisos.append(
                    f"SINAPI {codigo} adicionado sem estado de referência (custo zero)."
                )

            orcamento.adicionar_item_sinapi(
                grupo_id,
                codigo,
                descricao or codigo,
                unidade,
                custo,
                quantidade,
                estado,
                tipo_sinapi,
            )
        elif tipo == TIPO_ITEM_PROPRIA:
            codigo = str(ref.get("codigo", "")).strip()
            nome_item = str(ref.get("nome", "")).strip()
            unidade = str(ref.get("unidade", "")).strip()
            catalogo_id = str(ref.get("composicao_catalogo_id", "")).strip()

            composicao = None
            if catalogo_id:
                composicao = obter_composicao_por_id(catalogo, catalogo_id)
            if composicao is None and codigo:
                composicao = obter_por_codigo(codigo, dados_catalogo)

            if composicao is None:
                rotulo = nome_item or codigo or "sem código"
                avisos.append(
                    f"Composição própria não cadastrada: {rotulo} "
                    "(item adicionado para substituição na grade)."
                )
                orcamento.adicionar_composicao_propria(
                    grupo_id,
                    "",
                    codigo,
                    nome_item or codigo,
                    unidade,
                    quantidade,
                )
            else:
                orcamento.adicionar_composicao_propria(
                    grupo_id,
                    composicao.get("id", catalogo_id),
                    composicao.get("codigo", codigo),
                    composicao.get("nome", nome_item),
                    composicao.get("unidade", unidade) or unidade,
                    quantidade,
                )

    return grupo_id, avisos


def copiar_etapa(etapa: dict) -> dict:
    return deepcopy(etapa)
