"""Persistência local dos rascunhos de Área Comum (JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from app_paths import area_comum_autosave_path, area_comum_rascunhos_dir
from core.area_comum import VERSAO_RASCUNHO, normalizar_rascunho, rascunho_para_salvar


class RascunhoAreaComumError(ValueError):
    """Arquivo de rascunho inválido ou incompatível."""


def pasta_rascunhos() -> Path:
    return area_comum_rascunhos_dir()


def caminho_autosave() -> Path:
    return area_comum_autosave_path()


def _ler_json(caminho: Path) -> dict:
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RascunhoAreaComumError(f"Não foi possível ler o arquivo:\n{caminho}") from exc
    except json.JSONDecodeError as exc:
        raise RascunhoAreaComumError("O arquivo JSON está corrompido ou incompleto.") from exc
    if not isinstance(bruto, dict):
        raise RascunhoAreaComumError("O arquivo não contém um rascunho de Área Comum.")
    versao = bruto.get("versao", 0)
    try:
        versao_int = int(versao)
    except (TypeError, ValueError):
        versao_int = 0
    if versao_int > VERSAO_RASCUNHO:
        raise RascunhoAreaComumError(
            "Este rascunho foi salvo em uma versão mais nova do ORC."
        )
    return normalizar_rascunho(bruto)


def carregar_rascunho(caminho) -> dict:
    return _ler_json(Path(caminho))


def salvar_rascunho(dados: dict, caminho) -> Path:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = rascunho_para_salvar(dados)
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destino


def carregar_autosave() -> dict | None:
    caminho = caminho_autosave()
    if not caminho.is_file():
        return None
    try:
        return _ler_json(caminho)
    except RascunhoAreaComumError:
        return None


def salvar_autosave(dados: dict) -> Path:
    return salvar_rascunho(dados, caminho_autosave())


def limpar_autosave() -> None:
    caminho = caminho_autosave()
    try:
        if caminho.is_file():
            caminho.unlink()
    except OSError:
        pass
