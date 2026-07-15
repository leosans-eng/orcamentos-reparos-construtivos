"""Persistência local das etapas pré-definidas em JSON (modo offline)."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy

from app_paths import etapas_predefinidas_path

VERSAO_ARQUIVO = 1

_catalogo_cache: dict | None = None


def limpar_cache():
    global _catalogo_cache
    _catalogo_cache = None


def _invalidar_cache():
    limpar_cache()


def _arquivo_padrao():
    return {"versao": VERSAO_ARQUIVO, "etapas": []}


def _ler_arquivo() -> dict:
    caminho = etapas_predefinidas_path()
    if not caminho.is_file():
        return _arquivo_padrao()
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if not dados.get("etapas"):
        dados = _arquivo_padrao()
    return dados


def _salvar_arquivo(dados: dict) -> None:
    caminho = etapas_predefinidas_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _aplicar_catalogo(dados: dict) -> dict:
    global _catalogo_cache
    _catalogo_cache = deepcopy(dados)
    return _catalogo_cache


def obter_cache_catalogo() -> dict | None:
    if _catalogo_cache is None:
        return None
    return deepcopy(_catalogo_cache)


def carregar() -> dict:
    return _aplicar_catalogo(_ler_arquivo())


def salvar(dados: dict) -> None:
    _salvar_arquivo(dados)
    _aplicar_catalogo(dados)


def listar(dados=None) -> list:
    if dados is None:
        dados = _catalogo_cache or carregar()
    return deepcopy(dados.get("etapas", []))


def obter_por_id(etapa_id, dados=None) -> dict | None:
    for etapa in listar(dados):
        if etapa.get("id") == etapa_id:
            return etapa
    return None


def criar(nome: str, dados=None) -> str:
    if dados is None:
        dados = carregar()
    nome = str(nome).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")
    etapa_id = str(uuid.uuid4())
    etapa = {"id": etapa_id, "nome": nome, "itens": [], "versao": 1}
    dados.setdefault("etapas", []).append(etapa)
    salvar(dados)
    return etapa_id


def atualizar(etapa: dict, dados=None) -> str:
    if dados is None:
        dados = carregar()
    etapa_id = etapa.get("id")
    if not etapa_id:
        raise ValueError("Etapa sem identificador.")
    nome = str(etapa.get("nome", "")).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")

    payload = deepcopy(etapa)
    payload.pop("versao", None)
    encontrado = False
    for indice, registro in enumerate(dados.get("etapas", [])):
        if registro.get("id") == etapa_id:
            payload["versao"] = int(registro.get("versao", 1)) + 1
            dados["etapas"][indice] = payload
            encontrado = True
            break
    if not encontrado:
        payload["versao"] = 1
        dados.setdefault("etapas", []).append(payload)
    salvar(dados)
    return etapa_id


def excluir(etapa_id, dados=None) -> None:
    if dados is None:
        dados = carregar()
    if obter_por_id(etapa_id, dados) is None:
        raise ValueError("Etapa não encontrada.")
    dados["etapas"] = [e for e in dados.get("etapas", []) if e.get("id") != etapa_id]
    salvar(dados)
