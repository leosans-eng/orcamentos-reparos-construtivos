"""Caminhos do app em desenvolvimento e no executável PyInstaller."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Pasta do programa — dados graváveis (SINAPI, status) ficam aqui."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    """Recursos empacotados (JSON de vícios, ícone)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return Path(__file__).resolve().parent


def icon_path() -> Path | None:
    for candidate in (
        bundle_dir() / "icone.ico",
        app_dir() / "icone.ico",
    ):
        if candidate.is_file():
            return candidate
    return None


def asset_path(*parts: str) -> Path | None:
    for base in (bundle_dir(), app_dir()):
        candidate = base.joinpath("assets", *parts)
        if candidate.is_file():
            return candidate
    return None


def sinapi_referencia_dir() -> Path:
    pasta = app_dir() / "sinapi" / "sinapi_referencia"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def vicios_construtivos_path() -> Path:
    for candidate in (
        bundle_dir() / "vicios_construtivos.json",
        app_dir() / "vicios_construtivos.json",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "vicios_construtivos.json não encontrado. "
        f"Procurado em {bundle_dir()} e {app_dir()}."
    )


def dados_usuario_dir() -> Path:
    """
    Pasta de dados graváveis pelo usuário, fora do pacote de instalação.
    No executável usa %LOCALAPPDATA%\\ORC; em desenvolvimento usa dados_usuario/.
    """
    if is_frozen():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        pasta = base / "ORC"
    else:
        pasta = app_dir() / "dados_usuario"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def orcamentos_customizados_path() -> Path:
    return dados_usuario_dir() / "orcamentos_customizados.json"


def composicoes_proprias_path() -> Path:
    return dados_usuario_dir() / "composicoes_proprias.json"
