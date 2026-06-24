"""Resolução de arquivos de planilha de entrada para importação futura.

O layout esperado segue o padrão de exportação do sistema i9 (software externo ao ORC).
Esse módulo será usado pelo módulo de importação de planilhas; a geração de modelos
a partir do Orçamento Customizado não depende dele.
"""

from __future__ import annotations

import os
from pathlib import Path

PREFIXO_SAIDA = "Planilha_Sintetica_Convertida_Modelo"
PADROES_ENTRADA = (
    "Planilha Sintética Simples*.xlsx",
    "Planilha Sintética*.xlsx",
)


class ArquivoEntradaAmbiguo(Exception):
    """Vários arquivos candidatos encontrados na pasta."""

    def __init__(self, candidatos: list[Path]):
        self.candidatos = candidatos
        nomes = "\n".join(f"  - {caminho.name}" for caminho in candidatos)
        super().__init__(
            "Vários arquivos de entrada encontrados. Informe o caminho explicitamente:\n"
            f"{nomes}"
        )


def _eh_arquivo_saida(caminho: Path) -> bool:
    return caminho.name.startswith(PREFIXO_SAIDA)


def _candidatos_na_pasta(diretorio: Path) -> list[Path]:
    encontrados: dict[Path, None] = {}
    for padrao in PADROES_ENTRADA:
        for caminho in diretorio.glob(padrao):
            if caminho.is_file() and not _eh_arquivo_saida(caminho):
                encontrados[caminho.resolve()] = None
    return sorted(
        encontrados.keys(),
        key=lambda caminho: caminho.stat().st_mtime,
        reverse=True,
    )


def resolver_arquivo_entrada(
    caminho_informado: str | None = None,
    *,
    diretorio: str | Path | None = None,
) -> tuple[str, str]:
    """
    Define qual planilha usar na importação.

    Ordem de prioridade:
    1. Caminho informado pelo chamador
    2. Variável de ambiente ORC_ARQUIVO_PLANILHA_ENTRADA
    3. Detecção automática na pasta indicada (ou diretório atual)
    """
    if caminho_informado:
        return os.path.abspath(caminho_informado), "caminho informado"

    env = (os.environ.get("ORC_ARQUIVO_PLANILHA_ENTRADA") or "").strip()
    if env:
        return os.path.abspath(env), "variável ORC_ARQUIVO_PLANILHA_ENTRADA"

    base = Path(diretorio or os.getcwd())
    candidatos = _candidatos_na_pasta(base)
    if not candidatos:
        raise FileNotFoundError(
            "Nenhuma planilha de entrada encontrada.\n"
            "Informe o caminho do arquivo ou coloque uma planilha "
            "'Planilha Sintética*.xlsx' na pasta selecionada."
        )
    if len(candidatos) > 1:
        raise ArquivoEntradaAmbiguo(candidatos)

    return str(candidatos[0]), "detectado automaticamente na pasta"
