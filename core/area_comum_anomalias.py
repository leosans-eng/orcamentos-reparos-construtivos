"""Catálogo de anomalias da Área Comum (JSON local, editável por admin)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app_paths import (
    anomalias_area_comum_path,
    anomalias_area_comum_path_gravacao,
)
from core.area_comum import novo_id

VERSAO_CATALOGO = 1

ORIGEM_ITENS = "itens"
ORIGEM_ETAPA = "etapa_predefinida"

TIPOS_CALCULO = (
    "area_fachada_total",
    "area_alvenaria_hall_total",
    "area_laje_hall_total",
    "area_piso_hall_total",
    "perimetro_hall_rodape_total",
    "area_cobertura_total",
    "perimetro_paredes_externas_total",
    "perimetro_platibanda_total",
    "perimetro_beiral",
    "pingadeira_total",
    "esquadria_area_total",
    "pct_troca_revestimento_fachada",
    "pct_troca_revestimento_paredes_hall",
    "pct_troca_revestimento_tetos_hall",
    "pct_troca_pisos_hall",
    "pct_troca_rodape_hall",
    "pct_troca_estrutura_cobertura",
    "pct_instalacao_tabeira_beiral",
    "pct_troca_telhas_cobertura",
    "pct_troca_rufos_pingadeira",
    "pct_pintura_fachada",
    "pct_pintura_paredes_hall",
    "pct_pintura_teto_hall",
    "por_bloco",
    "por_pavimento",
    "por_apartamento",
    "fixo",
)

ROTULOS_TIPO_CALCULO = {
    "area_fachada_total": "Área de fachada (total, sem esquadrias)",
    "area_alvenaria_hall_total": "Área de alvenaria do hall (total)",
    "area_laje_hall_total": "Área da laje do hall (total)",
    "area_piso_hall_total": "Área de piso do hall (total)",
    "perimetro_hall_rodape_total": "Perímetro de rodapé do hall (total)",
    "area_cobertura_total": "Área de cobertura (total)",
    "perimetro_paredes_externas_total": "Perímetro de paredes externas (total)",
    "perimetro_platibanda_total": "Perímetro de platibanda (total)",
    "perimetro_beiral": "Perímetro de beiral (calha)",
    "pingadeira_total": "Pingadeira (total)",
    "esquadria_area_total": "Área de esquadrias (total)",
    "pct_troca_revestimento_fachada": "% Troca de revestimento da fachada",
    "pct_troca_revestimento_paredes_hall": "% Troca de revestimento das paredes dos halls",
    "pct_troca_revestimento_tetos_hall": "% Troca de revestimento dos tetos dos halls",
    "pct_troca_pisos_hall": "% Troca de pisos do hall",
    "pct_troca_rodape_hall": "% Troca de rodapé do hall",
    "pct_troca_estrutura_cobertura": "% Troca de estrutura da cobertura",
    "pct_instalacao_tabeira_beiral": "% Instalação de tabeira / beiral",
    "pct_troca_telhas_cobertura": "% Troca de telhas da cobertura",
    "pct_troca_rufos_pingadeira": "% Troca de rufos e pingadeiras",
    "pct_pintura_fachada": "% Pintura da fachada",
    "pct_pintura_paredes_hall": "% Pintura das paredes do hall",
    "pct_pintura_teto_hall": "% Pintura do teto do hall",
    "por_bloco": "Por bloco",
    "por_pavimento": "Por pavimento",
    "por_apartamento": "Por apartamento",
    "fixo": "Quantidade fixa",
}

MAPA_TIPO_QUANTITATIVO = {
    "area_fachada_total": "area_fachada_total_m2",
    "area_alvenaria_hall_total": "area_alvenaria_hall_total_m2",
    "area_laje_hall_total": "area_laje_hall_total_m2",
    "area_piso_hall_total": "area_piso_hall_total_m2",
    "perimetro_hall_rodape_total": "perimetro_hall_rodape_total_m",
    "area_cobertura_total": "area_cobertura_total_m2",
    "perimetro_paredes_externas_total": "perimetro_paredes_externas_total_m",
    "perimetro_platibanda_total": "perimetro_platibanda_total_m",
    "perimetro_beiral": "perimetro_beiral_m",
    "pingadeira_total": "pingadeira_total_m",
    "esquadria_area_total": "esquadria_area_total_m2",
    "pct_troca_revestimento_fachada": "pct_troca_revestimento_fachada_m2",
    "pct_troca_revestimento_paredes_hall": "pct_troca_revestimento_paredes_hall_m2",
    "pct_troca_revestimento_tetos_hall": "pct_troca_revestimento_tetos_hall_m2",
    "pct_troca_pisos_hall": "pct_troca_pisos_hall_m2",
    "pct_troca_rodape_hall": "pct_troca_rodape_hall_m",
    "pct_troca_estrutura_cobertura": "pct_troca_estrutura_cobertura_m2",
    "pct_instalacao_tabeira_beiral": "pct_instalacao_tabeira_beiral_m",
    "pct_troca_telhas_cobertura": "pct_troca_telhas_cobertura_m2",
    "pct_troca_rufos_pingadeira": "pct_troca_rufos_pingadeira_m",
    "pct_pintura_fachada": "pct_pintura_fachada_m2",
    "pct_pintura_paredes_hall": "pct_pintura_paredes_hall_m2",
    "pct_pintura_teto_hall": "pct_pintura_teto_hall_m2",
    "por_bloco": "qtd_blocos",
    "por_pavimento": "qtd_pavimentos",
    "por_apartamento": "qtd_aptos_total",
}

UNIDADES_COMUNS = ("m²", "m", "m³", "H", "Un", "un", "KG", "L")


def catalogo_vazio() -> dict[str, Any]:
    return {"versao": VERSAO_CATALOGO, "anomalias": {}}


def novo_item_sinapi(
    *,
    codigo_sinapi: str = "",
    unidade: str = "m²",
    tipo_calculo: str = "area_fachada_total",
    coeficiente: float = 1.0,
) -> dict[str, Any]:
    try:
        if isinstance(coeficiente, str):
            texto = coeficiente.strip().replace(".", "").replace(",", ".") if "," in str(coeficiente) else coeficiente
            coef = float(texto)
        else:
            coef = float(coeficiente)
    except (TypeError, ValueError):
        coef = 1.0
    return {
        "id": novo_id(),
        "codigo_sinapi": str(codigo_sinapi).strip(),
        "unidade": str(unidade or "m²").strip(),
        "tipo_calculo": tipo_calculo if tipo_calculo in TIPOS_CALCULO else "fixo",
        "coeficiente": coef,
    }


def novo_reparo(*, nome: str = "Reparo padrão", origem: str = ORIGEM_ITENS) -> dict[str, Any]:
    return {
        "id": novo_id(),
        "nome": str(nome or "Reparo padrão").strip(),
        "origem": origem if origem in (ORIGEM_ITENS, ORIGEM_ETAPA) else ORIGEM_ITENS,
        "etapa_predefinida_id": "",
        "etapa_nome": "",
        "tipo_calculo_etapa": "fixo",
        "itens": [],
    }


def nova_anomalia(nome: str) -> dict[str, Any]:
    return {
        "reparos": [novo_reparo(nome="Reparo padrão")],
    }


def carregar_catalogo(caminho: Path | None = None) -> dict[str, Any]:
    origem = caminho or anomalias_area_comum_path()
    if not Path(origem).is_file():
        return catalogo_vazio()
    try:
        with open(origem, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return catalogo_vazio()
    return normalizar_catalogo(dados)


def salvar_catalogo(dados: dict[str, Any], caminho: Path | None = None) -> Path:
    destino = caminho or anomalias_area_comum_path_gravacao()
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = normalizar_catalogo(dados)
    payload["versao"] = VERSAO_CATALOGO
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return destino


def normalizar_catalogo(dados) -> dict[str, Any]:
    base = catalogo_vazio()
    if not isinstance(dados, dict):
        return base
    anomalias = dados.get("anomalias")
    if not isinstance(anomalias, dict):
        return base
    for nome, bruto in anomalias.items():
        titulo = str(nome or "").strip()
        if not titulo:
            continue
        if not isinstance(bruto, dict):
            bruto = {}
        reparos = []
        origem_reparos = bruto.get("reparos")
        if not origem_reparos and bruto.get("etapas"):
            reparo = novo_reparo(nome="Reparo padrão", origem=ORIGEM_ITENS)
            reparo["itens"] = [
                novo_item_sinapi(
                    codigo_sinapi=item.get("codigo_sinapi"),
                    unidade=item.get("unidade") or "m²",
                    tipo_calculo=item.get("tipo_calculo") or "fixo",
                    coeficiente=item.get("coeficiente") or 1,
                )
                for item in bruto.get("etapas") or []
                if isinstance(item, dict)
            ]
            reparos.append(reparo)
        else:
            for item in origem_reparos or []:
                if not isinstance(item, dict):
                    continue
                reparo = novo_reparo(
                    nome=item.get("nome") or "Reparo padrão",
                    origem=item.get("origem") or ORIGEM_ITENS,
                )
                if item.get("id"):
                    reparo["id"] = str(item.get("id"))
                reparo["etapa_predefinida_id"] = str(item.get("etapa_predefinida_id") or "")
                reparo["etapa_nome"] = str(item.get("etapa_nome") or "")
                tipo_et = str(item.get("tipo_calculo_etapa") or "fixo")
                reparo["tipo_calculo_etapa"] = (
                    tipo_et if tipo_et in TIPOS_CALCULO else "fixo"
                )
                itens = []
                for etapa in item.get("itens") or []:
                    if not isinstance(etapa, dict):
                        continue
                    novo = novo_item_sinapi(
                        codigo_sinapi=etapa.get("codigo_sinapi"),
                        unidade=etapa.get("unidade") or "m²",
                        tipo_calculo=etapa.get("tipo_calculo") or "fixo",
                        coeficiente=etapa.get("coeficiente") or 1,
                    )
                    if etapa.get("id"):
                        novo["id"] = str(etapa.get("id"))
                    itens.append(novo)
                reparo["itens"] = itens
                reparos.append(reparo)
        if not reparos:
            reparos = [novo_reparo(nome="Reparo padrão")]
        base["anomalias"][titulo] = {"reparos": reparos}
    return base


def nomes_anomalias(dados: dict | None = None) -> list[str]:
    origem = dados if dados is not None else carregar_catalogo()
    return list((origem.get("anomalias") or {}).keys())


def obter_anomalia(nome: str, dados: dict | None = None) -> dict | None:
    origem = dados if dados is not None else carregar_catalogo()
    return deepcopy((origem.get("anomalias") or {}).get(nome))


def quantidade_item(tipo_calculo: str, coeficiente: float, quantitativos: dict) -> float:
    coef = float(coeficiente or 0)
    if tipo_calculo == "fixo":
        return coef
    chave = MAPA_TIPO_QUANTITATIVO.get(tipo_calculo)
    if not chave:
        return coef
    base = float(quantitativos.get(chave) or 0)
    return base * coef
