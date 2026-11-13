"""Persistência local dos rascunhos de Área Comum (JSON)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app_paths import area_comum_autosave_path, area_comum_rascunhos_dir
from core.area_comum import VERSAO_RASCUNHO, normalizar_rascunho, rascunho_para_salvar


class RascunhoAreaComumError(ValueError):
    """Arquivo de rascunho inválido ou incompatível."""


def pasta_rascunhos() -> Path:
    return area_comum_rascunhos_dir()


def caminho_autosave() -> Path:
    return area_comum_autosave_path()


# Campo extra só do autosave: de qual arquivo .json o trabalho veio.
CHAVE_ORIGEM_AUTOSAVE = "arquivo_origem"


def _ler_json(caminho: Path) -> dict:
    return normalizar_rascunho(_ler_json_bruto(caminho))


def _ler_json_bruto(caminho: Path) -> dict:
    """Lê e valida o arquivo, sem normalizar (preserva campos extras)."""
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
    return bruto


def carregar_rascunho(caminho) -> dict:
    return _ler_json(Path(caminho))


def _gravar_json(destino: Path, payload: dict) -> None:
    """Grava num arquivo temporário e só depois substitui o destino.

    Se o programa fechar no meio da gravação, o arquivo anterior continua
    inteiro (em vez de ficar um JSON pela metade).
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    temporario.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporario, destino)


def salvar_rascunho(dados: dict, caminho) -> Path:
    destino = Path(caminho)
    _gravar_json(destino, rascunho_para_salvar(dados))
    return destino


def carregar_autosave() -> tuple[dict, str | None] | None:
    """Devolve (rascunho normalizado, caminho do arquivo de origem ou None)."""
    caminho = caminho_autosave()
    if not caminho.is_file():
        return None
    try:
        bruto = _ler_json_bruto(caminho)
    except RascunhoAreaComumError:
        return None
    origem = str(bruto.get(CHAVE_ORIGEM_AUTOSAVE) or "").strip() or None
    return normalizar_rascunho(bruto), origem


def salvar_autosave(dados: dict, caminho_origem=None) -> Path:
    destino = caminho_autosave()
    payload = rascunho_para_salvar(dados)
    payload[CHAVE_ORIGEM_AUTOSAVE] = str(caminho_origem) if caminho_origem else ""
    _gravar_json(destino, payload)
    return destino


def limpar_autosave() -> None:
    caminho = caminho_autosave()
    try:
        if caminho.is_file():
            caminho.unlink()
    except OSError:
        pass
