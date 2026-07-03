"""Persistência do catálogo de composições próprias via API."""

from copy import deepcopy

from core.api_client import get_client
from core.api_exceptions import ApiError, ConflitoVersaoError

VERSAO_ARQUIVO = 1
ESTADO_PREVIA_PADRAO = "SP"

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


def carregar():
    try:
        dados = get_client().get_composicoes_catalogo()
    except ApiError as exc:
        _tratar_erro_api(exc)
    return _aplicar_catalogo(dados)


def salvar(dados):
    """Compatibilidade: o catálogo é persistido registro a registro na API."""
    _aplicar_catalogo(dados)


def obter_estado_previa_custos(dados=None):
    if dados is None:
        if _catalogo_cache is None:
            dados = carregar()
        else:
            dados = _catalogo_cache
    estado = str(dados.get("estado_previa_custos", "")).strip()
    return estado or ESTADO_PREVIA_PADRAO


def salvar_estado_previa_custos(estado, dados=None):
    estado = str(estado or "").strip()
    if not estado:
        return
    try:
        catalogo = get_client().salvar_estado_previa_custos(estado)
    except ApiError as exc:
        _tratar_erro_api(exc)
    _aplicar_catalogo(catalogo)


def listar(dados=None):
    if dados is None:
        if _catalogo_cache is None:
            dados = carregar()
        else:
            dados = _catalogo_cache
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
    codigo = str(codigo).strip()
    if not codigo:
        raise ValueError("Informe o código da composição.")
    if obter_por_codigo(codigo, dados):
        raise ValueError(f"Já existe uma composição com o código {codigo}.")
    if not nome or not str(nome).strip():
        raise ValueError("Informe o nome da composição.")
    if not unidade or not str(unidade).strip():
        raise ValueError("Informe a unidade da composição.")

    try:
        composicao = get_client().criar_composicao(codigo, nome, unidade, componentes)
    except ApiError as exc:
        _tratar_erro_api(exc)

    _invalidar_cache()
    carregar()
    return composicao["id"]


def atualizar(composicao, dados=None):
    comp_id = composicao.get("id")
    if not comp_id:
        raise ValueError("Composição sem identificador.")

    codigo = str(composicao.get("codigo", "")).strip()
    if not codigo:
        raise ValueError("Informe o código da composição.")

    versao = composicao.get("versao")
    if versao is None:
        existente = obter_por_id(comp_id, dados)
        versao = existente.get("versao", 1) if existente else 1

    payload = deepcopy(composicao)
    payload.pop("versao", None)

    try:
        get_client().atualizar_composicao(str(comp_id), payload, int(versao))
    except ApiError as exc:
        _tratar_erro_api(exc)

    _invalidar_cache()
    carregar()
    return comp_id


def excluir(composicao_id, dados=None):
    if obter_por_id(composicao_id, dados) is None:
        raise ValueError("Composição não encontrada.")
    try:
        get_client().excluir_composicao(str(composicao_id))
    except ApiError as exc:
        _tratar_erro_api(exc)
    _invalidar_cache()
    carregar()
