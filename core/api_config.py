"""Configuração e sessão da API ORC (URL, token)."""

from __future__ import annotations

import json
from pathlib import Path

from app_paths import dados_usuario_dir

URL_PADRAO = "http://localhost:8000"


def api_config_path() -> Path:
    return dados_usuario_dir() / "orc_api.json"


def sessao_path() -> Path:
    return dados_usuario_dir() / "orc_sessao.json"


def carregar_config() -> dict:
    caminho = api_config_path()
    if not caminho.is_file():
        return {"base_url": URL_PADRAO}
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    base_url = str(dados.get("base_url", URL_PADRAO)).strip().rstrip("/")
    return {"base_url": base_url or URL_PADRAO}


def salvar_config(base_url: str) -> None:
    caminho = api_config_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    base_url = str(base_url or "").strip().rstrip("/") or URL_PADRAO
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump({"base_url": base_url}, arquivo, ensure_ascii=False, indent=2)


def carregar_sessao() -> dict | None:
    caminho = sessao_path()
    if not caminho.is_file():
        return None
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    token = str(dados.get("access_token", "")).strip()
    username = str(dados.get("username", "")).strip()
    if not token:
        return None
    return {"access_token": token, "username": username}


def salvar_sessao(access_token: str, username: str) -> None:
    caminho = sessao_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            {"access_token": access_token, "username": username},
            arquivo,
            ensure_ascii=False,
            indent=2,
        )


def limpar_sessao() -> None:
    caminho = sessao_path()
    if caminho.is_file():
        caminho.unlink()
