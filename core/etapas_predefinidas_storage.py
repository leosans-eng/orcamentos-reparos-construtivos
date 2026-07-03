"""Persistência das etapas pré-definidas via API."""

from __future__ import annotations

from copy import deepcopy

from core.api_client import get_client
from core.api_exceptions import ApiError, ConflitoVersaoError

VERSAO_ARQUIVO = 1

_catalogo_cache: dict | None = None


def _tratar_erro_api(exc: ApiError) -> None:
    if isinstance(exc, ConflitoVersaoError):
        raise ValueError(exc.mensagem) from exc
    raise ValueError(exc.mensagem) from exc


def _invalidar_cache():
    global _catalogo_cache
    _catalogo_cache = None


def _aplicar_catalogo(dados: dict) -> dict:
    global _catalogo_cache
    _catalogo_cache = deepcopy(dados)
    return _catalogo_cache


def obter_cache_catalogo() -> dict | None:
    if _catalogo_cache is None:
        return None
    return deepcopy(_catalogo_cache)


def carregar() -> dict:
    try:
        dados = get_client().get_etapas_catalogo()
    except ApiError as exc:
        _tratar_erro_api(exc)
    return _aplicar_catalogo(dados)


def salvar(dados: dict) -> None:
    _aplicar_catalogo(dados)


def listar(dados=None) -> list:
    if dados is None:
        if _catalogo_cache is None:
            dados = carregar()
        else:
            dados = _catalogo_cache
    return deepcopy(dados.get("etapas", []))


def obter_por_id(etapa_id, dados=None) -> dict | None:
    for etapa in listar(dados):
        if etapa.get("id") == etapa_id:
            return etapa
    return None


def criar(nome: str, dados=None) -> str:
    nome = str(nome).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")
    try:
        etapa = get_client().criar_etapa(nome)
    except ApiError as exc:
        _tratar_erro_api(exc)
    _invalidar_cache()
    carregar()
    return etapa["id"]


def atualizar(etapa: dict, dados=None) -> str:
    etapa_id = etapa.get("id")
    if not etapa_id:
        raise ValueError("Etapa sem identificador.")
    nome = str(etapa.get("nome", "")).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")

    versao = etapa.get("versao")
    if versao is None:
        existente = obter_por_id(etapa_id, dados)
        versao = existente.get("versao", 1) if existente else 1

    payload = deepcopy(etapa)
    payload.pop("versao", None)

    try:
        get_client().atualizar_etapa(str(etapa_id), payload, int(versao))
    except ApiError as exc:
        _tratar_erro_api(exc)

    _invalidar_cache()
    carregar()
    return etapa_id


def excluir(etapa_id, dados=None) -> None:
    if obter_por_id(etapa_id, dados) is None:
        raise ValueError("Etapa não encontrada.")
    try:
        get_client().excluir_etapa(str(etapa_id))
    except ApiError as exc:
        _tratar_erro_api(exc)
    _invalidar_cache()
    carregar()
