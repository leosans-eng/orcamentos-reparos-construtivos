"""Configuração e sessão da API ORC (URL, token, credenciais salvas)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from app_paths import dados_usuario_dir

URL_PADRAO = "http://localhost:8000"


def api_config_path() -> Path:
    return dados_usuario_dir() / "orc_api.json"


def sessao_path() -> Path:
    return dados_usuario_dir() / "orc_sessao.json"


def _codificar_senha(senha: str) -> str:
    return base64.b64encode(senha.encode("utf-8")).decode("ascii")


def _decodificar_senha(valor: str) -> str:
    try:
        return base64.b64decode(valor.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""


def carregar_config() -> dict:
    caminho = api_config_path()
    padrao = {
        "base_url": URL_PADRAO,
        "salvar_usuario": True,
        "salvar_senha": False,
        "usuario": "",
        "senha": "",
    }
    if not caminho.is_file():
        return padrao
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    base_url = str(dados.get("base_url", URL_PADRAO)).strip().rstrip("/")
    salvar_usuario = bool(dados.get("salvar_usuario", False))
    salvar_senha = bool(dados.get("salvar_senha", False))
    usuario = str(dados.get("usuario", "")).strip() if salvar_usuario else ""
    senha = ""
    if salvar_senha:
        senha = _decodificar_senha(str(dados.get("senha", "")))
    return {
        "base_url": base_url or URL_PADRAO,
        "salvar_usuario": salvar_usuario,
        "salvar_senha": salvar_senha and salvar_usuario,
        "usuario": usuario,
        "senha": senha,
    }


def salvar_config(
    base_url: str,
    *,
    salvar_usuario: bool = False,
    salvar_senha: bool = False,
    usuario: str = "",
    senha: str = "",
) -> None:
    caminho = api_config_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    base_url = str(base_url or "").strip().rstrip("/") or URL_PADRAO
    salvar_usuario = bool(salvar_usuario)
    salvar_senha = bool(salvar_senha) and salvar_usuario
    payload = {
        "base_url": base_url,
        "salvar_usuario": salvar_usuario,
        "salvar_senha": salvar_senha,
        "usuario": str(usuario or "").strip() if salvar_usuario else "",
        "senha": _codificar_senha(senha) if salvar_senha else "",
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(payload, arquivo, ensure_ascii=False, indent=2)


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
