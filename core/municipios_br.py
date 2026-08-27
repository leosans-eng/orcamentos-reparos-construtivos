"""Resolução de UF a partir do nome da cidade (municípios IBGE)."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app_paths import municipios_uf_path

SIGLAS_UF = frozenset({
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
})

# Grafias vistas no Idebras que diferem do nome oficial do IBGE.
ALIAS_CIDADE = {
    "PINDAMONHAGABA": "PINDAMONHANGABA",
}


@dataclass(frozen=True)
class ResultadoUfConjunto:
    cidade: str
    uf: str | None = None
    ufs_possiveis: tuple[str, ...] = ()
    motivo: str = "ok"


def normalizar_cidade(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).upper().strip()


@lru_cache(maxsize=1)
def _indice_municipios() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    caminho = municipios_uf_path()
    if caminho is None or not caminho.is_file():
        return {}, {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    unicos = {
        str(nome): str(uf)
        for nome, uf in (dados.get("unicos") or {}).items()
    }
    ambiguos = {
        str(nome): tuple(str(uf) for uf in ufs)
        for nome, ufs in (dados.get("ambiguos") or {}).items()
    }
    return unicos, ambiguos


def cidade_do_conjunto(nome_conjunto: str) -> str:
    if not nome_conjunto:
        return ""
    prefixo = str(nome_conjunto).split(" - ", 1)[0]
    cidade = normalizar_cidade(prefixo)
    if not cidade:
        return ""
    partes = cidade.split()
    if len(partes) >= 2 and partes[-1] in SIGLAS_UF:
        cidade = " ".join(partes[:-1])
    return ALIAS_CIDADE.get(cidade, cidade)


def resolver_uf_conjunto(nome_conjunto: str) -> ResultadoUfConjunto:
    """Identifica a UF pela cidade no início do nome do conjunto Idebras."""
    cidade = cidade_do_conjunto(nome_conjunto)
    if not cidade:
        return ResultadoUfConjunto(cidade="", motivo="sem_cidade")

    unicos, ambiguos = _indice_municipios()
    if cidade in unicos:
        return ResultadoUfConjunto(cidade=cidade, uf=unicos[cidade], motivo="ok")
    if cidade in ambiguos:
        return ResultadoUfConjunto(
            cidade=cidade,
            ufs_possiveis=ambiguos[cidade],
            motivo="ambigua",
        )
    return ResultadoUfConjunto(cidade=cidade, motivo="nao_encontrada")


def estado_uf_do_conjunto(nome_conjunto: str) -> str | None:
    return resolver_uf_conjunto(nome_conjunto).uf
