"""Arquivos de desenho do ORCCAD avulso (aberto pelo Hub).

O arquivo .orccad é um JSON simples:
    {"tipo": "orccad", "versao": 1, "desenho": {"externa": {...}, "hall": {...}}}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app_paths import orccad_desenhos_dir

EXTENSAO = ".orccad"
TIPO_ARQUIVO = "orccad"
VERSAO_ARQUIVO = 1


class DesenhoORCCADError(Exception):
    """Erro com mensagem pronta para mostrar ao usuário."""


def pasta_desenhos() -> Path:
    return orccad_desenhos_dir()


def salvar_desenho(desenho: dict, caminho) -> None:
    """Grava o desenho sem risco de deixar um arquivo pela metade.

    Escreve primeiro num arquivo temporário e só depois troca pelo definitivo.
    """
    caminho = Path(caminho)
    dados = {"tipo": TIPO_ARQUIVO, "versao": VERSAO_ARQUIVO, "desenho": desenho}
    temporario = caminho.with_name(caminho.name + ".tmp")
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def carregar_desenho(caminho) -> dict:
    """Lê um arquivo .orccad e devolve o desenho ({externa, hall})."""
    caminho = Path(caminho)
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        raise DesenhoORCCADError("O arquivo não foi encontrado.") from None
    except OSError as exc:
        raise DesenhoORCCADError(f"Não foi possível ler o arquivo:\n{exc}") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise DesenhoORCCADError(
            "O arquivo está danificado ou não é um desenho do ORCCAD."
        ) from None

    if not isinstance(dados, dict) or dados.get("tipo") != TIPO_ARQUIVO:
        raise DesenhoORCCADError("Este arquivo não é um desenho do ORCCAD.")
    desenho = dados.get("desenho")
    if not isinstance(desenho, dict):
        raise DesenhoORCCADError(
            "O arquivo está danificado ou não é um desenho do ORCCAD."
        )
    return desenho
