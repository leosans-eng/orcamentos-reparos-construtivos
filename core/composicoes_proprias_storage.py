"""Persistência do catálogo de composições próprias."""

import json
from copy import deepcopy

from app_paths import composicoes_proprias_path

from core.composicoes_proprias import (
    TIPO_COMPONENTE_SINAPI,
    nova_composicao,
    novo_componente_sinapi,
)

VERSAO_ARQUIVO = 1
ESTADO_PREVIA_PADRAO = "SP"


def _composicao_exemplo():
    componentes = [
        novo_componente_sinapi(
            "370",
            "AREIA MEDIA - POSTO JAZIDA/FORNECEDOR (RETIRADO NA JAZIDA, SEM TRANSPORTE)",
            "M3",
            0.11,
        ),
        novo_componente_sinapi(
            "4721",
            "PEDRA BRITADA N. 1 (9,5 a 19 MM) POSTO PEDREIRA/FORNECEDOR, SEM FRETE",
            "M3",
            0.031,
        ),
        novo_componente_sinapi(
            "7271",
            (
                "BLOCO CERAMICO / TIJOLO VAZADO PARA ALVENARIA DE VEDACAO, "
                "8 FUROS NA HORIZONTAL DE 9 X 19 X 19 CM (L X A X C)"
            ),
            "UN",
            20.0,
        ),
        novo_componente_sinapi(
            "88316",
            "SERVENTE COM ENCARGOS COMPLEMENTARES",
            "H",
            2.07,
        ),
        novo_componente_sinapi(
            "1379",
            "CIMENTO PORTLAND COMPOSTO CP II-32",
            "KG",
            0.41,
        ),
        novo_componente_sinapi(
            "88309",
            "PEDREIRO COM ENCARGOS COMPLEMENTARES",
            "H",
            0.98,
        ),
    ]
    return nova_composicao(
        "47",
        "CAIXA DE AREIA 40X40X40CM EM ALVENARIA - EXECUÇÃO - H",
        "H",
        componentes,
    )


def _dados_iniciais():
    return {
        "versao": VERSAO_ARQUIVO,
        "composicoes": [_composicao_exemplo()],
    }


def carregar():
    caminho = composicoes_proprias_path()
    if not caminho.is_file():
        dados = _dados_iniciais()
        salvar(dados)
        return dados

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    composicoes = dados.get("composicoes")
    if not composicoes:
        dados = _dados_iniciais()
        salvar(dados)
        return dados

    return dados


def salvar(dados):
    caminho = composicoes_proprias_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def obter_estado_previa_custos(dados=None):
    if dados is None:
        dados = carregar()
    estado = str(dados.get("estado_previa_custos", "")).strip()
    return estado or ESTADO_PREVIA_PADRAO


def salvar_estado_previa_custos(estado, dados=None):
    estado = str(estado or "").strip()
    if not estado:
        return
    if dados is None:
        dados = carregar()
    dados["estado_previa_custos"] = estado
    salvar(dados)


def listar(dados=None):
    if dados is None:
        dados = carregar()
    return deepcopy(dados.get("composicoes", []))


def obter_por_id(composicao_id, dados=None):
    for comp in listar(dados):
        if comp.get("id") == composicao_id:
            return comp
    return None


def obter_por_codigo(codigo, dados=None):
    codigo = str(codigo).strip()
    for comp in listar(dados):
        if str(comp.get("codigo", "")).strip() == codigo:
            return comp
    return None


def criar(codigo, nome, unidade, componentes=None, dados=None):
    if dados is None:
        dados = carregar()
    codigo = str(codigo).strip()
    if not codigo:
        raise ValueError("Informe o código da composição.")
    if obter_por_codigo(codigo, dados):
        raise ValueError(f"Já existe uma composição com o código {codigo}.")
    if not nome or not str(nome).strip():
        raise ValueError("Informe o nome da composição.")
    if not unidade or not str(unidade).strip():
        raise ValueError("Informe a unidade da composição.")

    composicao = nova_composicao(codigo, nome, unidade, componentes)
    dados.setdefault("composicoes", []).append(composicao)
    salvar(dados)
    return composicao["id"]


def atualizar(composicao, dados=None):
    if dados is None:
        dados = carregar()
    comp_id = composicao.get("id")
    if not comp_id:
        raise ValueError("Composição sem identificador.")

    codigo = str(composicao.get("codigo", "")).strip()
    if not codigo:
        raise ValueError("Informe o código da composição.")

    for outra in dados.get("composicoes", []):
        if outra.get("id") != comp_id and str(outra.get("codigo", "")).strip() == codigo:
            raise ValueError(f"Já existe outra composição com o código {codigo}.")

    for indice, existente in enumerate(dados.get("composicoes", [])):
        if existente.get("id") == comp_id:
            dados["composicoes"][indice] = deepcopy(composicao)
            salvar(dados)
            return comp_id

    raise ValueError("Composição não encontrada.")


def excluir(composicao_id, dados=None):
    if dados is None:
        dados = carregar()
    antes = len(dados.get("composicoes", []))
    dados["composicoes"] = [
        c for c in dados.get("composicoes", []) if c.get("id") != composicao_id
    ]
    if len(dados["composicoes"]) == antes:
        raise ValueError("Composição não encontrada.")
    salvar(dados)
