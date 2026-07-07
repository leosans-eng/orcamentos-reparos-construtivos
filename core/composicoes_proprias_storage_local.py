"""Persistência local do catálogo de composições próprias em JSON (modo offline)."""

import json
import uuid
from copy import deepcopy

from app_paths import composicoes_proprias_path

VERSAO_ARQUIVO = 1
ESTADO_PREVIA_PADRAO = "SP"

_catalogo_cache: dict | None = None


def limpar_cache():
    global _catalogo_cache
    _catalogo_cache = None


def _invalidar_cache():
    limpar_cache()


def _arquivo_padrao():
    return {
        "versao": VERSAO_ARQUIVO,
        "estado_previa_custos": ESTADO_PREVIA_PADRAO,
        "composicoes": [],
    }


def _ler_arquivo() -> dict:
    caminho = composicoes_proprias_path()
    if not caminho.is_file():
        return _arquivo_padrao()
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if not dados.get("composicoes"):
        dados = _arquivo_padrao()
    return dados


def _salvar_arquivo(dados: dict) -> None:
    caminho = composicoes_proprias_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _aplicar_catalogo(dados: dict) -> dict:
    global _catalogo_cache
    _catalogo_cache = deepcopy(dados)
    return _catalogo_cache


def obter_cache_catalogo():
    if _catalogo_cache is None:
        return None
    return deepcopy(_catalogo_cache)


def carregar():
    return _aplicar_catalogo(_ler_arquivo())


def salvar(dados):
    _salvar_arquivo(dados)
    _aplicar_catalogo(dados)


def obter_estado_previa_custos(dados=None):
    if dados is None:
        dados = _catalogo_cache or carregar()
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
        dados = _catalogo_cache or carregar()
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

    comp_id = str(uuid.uuid4())
    composicao = {
        "id": comp_id,
        "codigo": codigo,
        "nome": str(nome).strip(),
        "unidade": str(unidade).strip(),
        "componentes": componentes or [],
        "versao": 1,
    }
    dados.setdefault("composicoes", []).append(composicao)
    salvar(dados)
    return comp_id


def atualizar(composicao, dados=None):
    if dados is None:
        dados = carregar()
    comp_id = composicao.get("id")
    if not comp_id:
        raise ValueError("Composição sem identificador.")
    codigo = str(composicao.get("codigo", "")).strip()
    if not codigo:
        raise ValueError("Informe o código da composição.")

    payload = deepcopy(composicao)
    payload.pop("versao", None)
    encontrado = False
    for indice, comp in enumerate(dados.get("composicoes", [])):
        if comp.get("id") == comp_id:
            payload["versao"] = int(comp.get("versao", 1)) + 1
            dados["composicoes"][indice] = payload
            encontrado = True
            break
    if not encontrado:
        payload["versao"] = 1
        dados.setdefault("composicoes", []).append(payload)
    salvar(dados)
    return comp_id


def excluir(composicao_id, dados=None):
    if dados is None:
        dados = carregar()
    if obter_por_id(composicao_id, dados) is None:
        raise ValueError("Composição não encontrada.")
    dados["composicoes"] = [
        c for c in dados.get("composicoes", []) if c.get("id") != composicao_id
    ]
    salvar(dados)
