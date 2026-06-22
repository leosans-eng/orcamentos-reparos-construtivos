"""Caminhos do app em desenvolvimento e no executável PyInstaller."""

from __future__ import annotations

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
