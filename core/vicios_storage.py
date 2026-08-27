"""Leitura e gravação de vicios_construtivos.json."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app_paths import vicios_construtivos_path, vicios_construtivos_path_gravacao

TIPOS_CALCULO = (
    "area_piso",
    "area_rev_arg",
    "area_rev_cer",
    "perimetro",
    "por_comodo",
    "fixo",
)

ROTULOS_TIPO_CALCULO = {
    "area_piso": "Área de piso",
    "area_rev_arg": "Área de revestimento argamassado",
    "area_rev_cer": "Área de revestimento cerâmico",
    "perimetro": "Perímetro (a partir do piso)",
    "por_comodo": "Por cômodo",
    "fixo": "Quantidade fixa",
}

UNIDADES_COMUNS = ("m²", "m", "m³", "H", "Un", "un", "KG", "L")

COMODOS_AREA_PRIVATIVA = (
    "Sala",
    "Circulação",
    "Dormitório 1",
    "Dormitório 2",
    "Banheiro",
    "Cozinha",
    "Área de Serviço",
    "Área Externa",
    "Varanda",
    "Residência Inteira",
)


def comodos_permitidos_anomalia(dados_anomalia: dict[str, Any] | None, todos=None) -> list[str]:
    """Cômodos em que a anomalia pode ser marcada. Sem cadastro = todos."""
    origem = list(todos if todos is not None else COMODOS_AREA_PRIVATIVA)
    if not dados_anomalia:
        return origem
    permitidos = dados_anomalia.get("comodos_permitidos")
    if permitidos is None:
        return origem
    nomes = {str(item) for item in permitidos}
    return [comodo for comodo in origem if comodo in nomes]


def carregar_vicios(caminho: Path | None = None) -> dict[str, Any]:
    origem = caminho or vicios_construtivos_path()
    with open(origem, "r", encoding="utf-8") as f:
        dados = json.load(f)
    if isinstance(dados, list):
        dados = dados[0]
    if not isinstance(dados, dict):
        raise ValueError("vicios_construtivos.json inválido.")
    dados.setdefault("anomalias", {})
    dados.setdefault("itens_gerais", {})
    return dados


def salvar_vicios(dados: dict[str, Any], caminho: Path | None = None) -> Path:
    destino = caminho or vicios_construtivos_path_gravacao()
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(dados)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return destino


def nomes_anomalias(dados: dict[str, Any] | None = None) -> list[str]:
    origem = dados if dados is not None else carregar_vicios()
    return list((origem.get("anomalias") or {}).keys())


def nova_etapa(
    *,
    codigo_sinapi: str = "",
    unidade: str = "m²",
    tipo_calculo: str = "area_piso",
    coeficiente: float = 1.0,
    grupo_planilha: str = "",
) -> dict[str, Any]:
    etapa: dict[str, Any] = {
        "codigo_sinapi": str(codigo_sinapi).strip(),
        "unidade": unidade,
        "tipo_calculo": tipo_calculo,
        "coeficiente": coeficiente,
    }
    if grupo_planilha:
        etapa["grupo_planilha"] = grupo_planilha
    return etapa


def nova_anomalia(nome: str, grupo_reparo: str = "") -> dict[str, Any]:
    return {
        "grupo_reparo": grupo_reparo or nome,
        "etapas": [],
        "comodos_permitidos": list(COMODOS_AREA_PRIVATIVA),
    }
