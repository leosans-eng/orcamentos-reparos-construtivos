"""Persistência das etapas pré-definidas do usuário (dados_usuario)."""

from __future__ import annotations

import json
from copy import deepcopy

from app_paths import etapas_predefinidas_path

from core.etapas_predefinidas import nova_etapa_predefinida

VERSAO_ARQUIVO = 1


def _dados_iniciais() -> dict:
    return {
        "versao": VERSAO_ARQUIVO,
        "etapas": [],
    }


def carregar() -> dict:
    caminho = etapas_predefinidas_path()
    if not caminho.is_file():
        dados = _dados_iniciais()
        salvar(dados)
        return dados

    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados.get("etapas"), list):
        dados = _dados_iniciais()
        salvar(dados)
    return dados


def salvar(dados: dict) -> None:
    caminho = etapas_predefinidas_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def listar(dados=None) -> list:
    if dados is None:
        dados = carregar()
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
    etapa = nova_etapa_predefinida(nome)
    dados.setdefault("etapas", []).append(etapa)
    salvar(dados)
    return etapa["id"]


def atualizar(etapa: dict, dados=None) -> str:
    if dados is None:
        dados = carregar()
    etapa_id = etapa.get("id")
    if not etapa_id:
        raise ValueError("Etapa sem identificador.")
    nome = str(etapa.get("nome", "")).strip()
    if not nome:
        raise ValueError("Informe o nome da etapa.")

    for indice, existente in enumerate(dados.get("etapas", [])):
        if existente.get("id") == etapa_id:
            dados["etapas"][indice] = deepcopy(etapa)
            salvar(dados)
            return etapa_id

    raise ValueError("Etapa não encontrada.")


def excluir(etapa_id, dados=None) -> None:
    if dados is None:
        dados = carregar()
    antes = len(dados.get("etapas", []))
    dados["etapas"] = [e for e in dados.get("etapas", []) if e.get("id") != etapa_id]
    if len(dados["etapas"]) == antes:
        raise ValueError("Etapa não encontrada.")
    salvar(dados)
