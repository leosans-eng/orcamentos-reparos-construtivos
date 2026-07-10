"""Persistência dos orçamentos customizados via API."""

from __future__ import annotations

from copy import deepcopy

from core.api_client import get_client
from core.api_exceptions import ApiError, ConflitoVersaoError
from core.orcamento_conversao import (
    dict_para_orcamento,
    orcamento_para_payload_api,
)

_lista_cache: list[dict] | None = None
_detalhe_cache: dict[str, dict] = {}


def _tratar_erro_api(exc: ApiError) -> None:
    if isinstance(exc, ConflitoVersaoError):
        raise ValueError(exc.mensagem) from exc
    if getattr(exc, "status_code", None) and int(exc.status_code) >= 500:
        raise ValueError(
            exc.mensagem
            or (
                "O servidor está temporariamente indisponível.\n"
                "O banco de dados pode estar fora do ar. Tente novamente em instantes."
            )
        ) from exc
    raise ValueError(exc.mensagem) from exc


def limpar_cache():
    global _lista_cache
    _lista_cache = None
    _detalhe_cache.clear()


def _invalidar_lista_cache():
    global _lista_cache
    _lista_cache = None


def obter_cache_lista():
    return deepcopy(_lista_cache) if _lista_cache is not None else None


def obter_cache_orcamento(orcamento_id: str):
    registro = _detalhe_cache.get(str(orcamento_id))
    return deepcopy(registro) if registro is not None else None


def invalidar_orcamento_cache(orcamento_id: str):
    _detalhe_cache.pop(str(orcamento_id), None)
    _invalidar_lista_cache()


def _normalizar_data(valor) -> str:
    if valor is None:
        return ""
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


def _api_para_dict(registro: dict) -> dict:
    dados = deepcopy(registro)
    dados["id"] = str(dados.get("id", ""))
    dados["criado_em"] = _normalizar_data(dados.get("criado_em"))
    dados["atualizado_em"] = _normalizar_data(dados.get("atualizado_em"))
    return dados


def _atualizar_cache_detalhe(registro: dict) -> dict:
    normalizado = _api_para_dict(registro)
    _detalhe_cache[normalizado["id"]] = normalizado
    return normalizado


def carregar_arquivo():
    """Compatibilidade com código legado — preferir listar_orcamentos_resumo()."""
    return {"versao": 1, "orcamento_ativo_id": None, "orcamentos": []}


def listar_orcamentos_resumo(dados=None, *, forcar_rede: bool = False):
    del dados
    global _lista_cache
    if forcar_rede:
        _lista_cache = None
    if _lista_cache is not None:
        return deepcopy(_lista_cache)
    try:
        resposta = get_client().listar_orcamentos()
    except ApiError as exc:
        _tratar_erro_api(exc)
    resumos = []
    for item in resposta.get("orcamentos", []):
        resumos.append(
            {
                "id": str(item["id"]),
                "nome": item.get("nome", "Sem nome"),
                "versao": int(item.get("versao", 1)),
                "criado_em": _normalizar_data(item.get("criado_em")),
                "atualizado_em": _normalizar_data(item.get("atualizado_em")),
                "grupos": int(item.get("grupos", 0)),
                "itens": int(item.get("itens", 0)),
            }
        )
    _lista_cache = deepcopy(resumos)
    return resumos


def _versao_orcamento(orcamento_id: str) -> int:
    if orcamento_id in _detalhe_cache:
        return int(_detalhe_cache[orcamento_id].get("versao", 1))
    if _lista_cache:
        for item in _lista_cache:
            if item.get("id") == orcamento_id:
                return int(item.get("versao", 1))
    registro = obter_orcamento_dict(orcamento_id)
    return int(registro.get("versao", 1))


def obter_orcamento_dict(orcamento_id, dados=None, *, forcar_rede: bool = False):
    del dados
    orcamento_id = str(orcamento_id)
    if forcar_rede:
        _detalhe_cache.pop(orcamento_id, None)
    elif orcamento_id in _detalhe_cache:
        return deepcopy(_detalhe_cache[orcamento_id])
    try:
        registro = get_client().obter_orcamento(orcamento_id)
    except ApiError as exc:
        _tratar_erro_api(exc)
    return _atualizar_cache_detalhe(registro)


def atualizar_orcamento_na_lista(orcamento):
    orcamento_id = str(getattr(orcamento, "id", ""))
    versao = getattr(orcamento, "versao", None)
    if versao is None:
        versao = _versao_orcamento(orcamento_id)
    payload = orcamento_para_payload_api(orcamento)
    try:
        registro = get_client().atualizar_orcamento(orcamento_id, payload, versao)
    except ApiError as exc:
        _tratar_erro_api(exc)
    normalizado = _atualizar_cache_detalhe(registro)
    orcamento.versao = int(normalizado.get("versao", versao))
    _invalidar_lista_cache()
    return normalizado


def criar_orcamento(nome):
    try:
        registro = get_client().criar_orcamento(nome.strip())
    except ApiError as exc:
        _tratar_erro_api(exc)
    _atualizar_cache_detalhe(registro)
    _invalidar_lista_cache()
    return str(registro["id"])


def adicionar_orcamento_importado(orcamento):
    nome = (orcamento.nome or "Importado").strip() or "Importado"
    orcamento_id = criar_orcamento(nome)
    orcamento.id = orcamento_id
    atualizar_orcamento_na_lista(orcamento)
    return orcamento_id


def renomear_orcamento(orcamento_id, novo_nome):
    orcamento_id = str(orcamento_id)
    versao = _versao_orcamento(orcamento_id)
    try:
        registro = get_client().renomear_orcamento(orcamento_id, novo_nome.strip(), versao)
    except ApiError as exc:
        _tratar_erro_api(exc)
    normalizado = _atualizar_cache_detalhe(registro)
    _invalidar_lista_cache()
    return normalizado


def duplicar_orcamento(orcamento_id, nome):
    orcamento_id = str(orcamento_id)
    try:
        registro = get_client().duplicar_orcamento(orcamento_id, nome.strip())
    except ApiError as exc:
        _tratar_erro_api(exc)
    normalizado = _atualizar_cache_detalhe(registro)
    _invalidar_lista_cache()
    return str(normalizado["id"])


def excluir_orcamento(orcamento_id):
    orcamento_id = str(orcamento_id)
    try:
        get_client().excluir_orcamento(orcamento_id)
    except ApiError as exc:
        _tratar_erro_api(exc)
    _detalhe_cache.pop(orcamento_id, None)
    _invalidar_lista_cache()
    return None
