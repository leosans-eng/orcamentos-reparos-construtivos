"""Catálogo de anomalias da Área Comum (JSON local, editável por admin)."""

from __future__ import annotations

import json
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

from app_paths import (
    anomalias_area_comum_path,
    anomalias_area_comum_path_gravacao,
)
from core.area_comum import PERCENTUAIS_MODELO, TIPOS_COBERTURA, TIPOS_ESTRUTURA, novo_id
from core.area_comum_calculos import numero
from core.etapas_predefinidas import TIPO_ITEM_PROPRIA, TIPO_ITEM_SINAPI

VERSAO_CATALOGO = 1

CRITERIO_NENHUM = ""
CRITERIO_ESTRUTURA = "tipo_estrutura"
CRITERIO_COBERTURA = "tipo_cobertura"

ORIGEM_ITENS = "itens"
ORIGEM_ETAPA = "etapa_predefinida"

CHAVE_SERVICOS_PRELIMINARES = "servicos_preliminares"
CHAVE_PINTURA = "pintura"
CHAVE_DESTINACAO_ENTULHO = "destinacao_entulho"
CHAVE_LIMPEZA_GERAL = "limpeza_geral"

ORIGEM_SERVICOS_PRELIMINARES = CHAVE_SERVICOS_PRELIMINARES
ORIGEM_DESTINACAO_ENTULHO = CHAVE_DESTINACAO_ENTULHO
ORIGEM_LIMPEZA_GERAL = CHAVE_LIMPEZA_GERAL

TIPO_ITEM_CATALOGO_SINAPI = TIPO_ITEM_SINAPI
TIPO_ITEM_CATALOGO_PROPRIA = TIPO_ITEM_PROPRIA

NOME_SERVICOS_PRELIMINARES = "SERVIÇOS PRELIMINARES"
NOME_PINTURA = "PINTURA"
NOME_DESTINACAO_ENTULHO = "DESTINAÇÃO DO ENTULHO"
NOME_LIMPEZA_GERAL = "LIMPEZA GERAL"

# Etapas fixas do orçamento: início (SP) e fim (pintura, entulho, limpeza).
ETAPAS_ORCAMENTO_FIXAS = (
    {
        "chave": CHAVE_SERVICOS_PRELIMINARES,
        "nome": NOME_SERVICOS_PRELIMINARES,
        "rotulo": "Serviços preliminares",
        "posicao": "inicio",
        "ordem": 0,
    },
    {
        "chave": CHAVE_PINTURA,
        "nome": NOME_PINTURA,
        "rotulo": "Pintura",
        "posicao": "fim",
        "ordem": 0,
    },
    {
        "chave": CHAVE_DESTINACAO_ENTULHO,
        "nome": NOME_DESTINACAO_ENTULHO,
        "rotulo": "Destinação do entulho",
        "posicao": "fim",
        "ordem": 1,
    },
    {
        "chave": CHAVE_LIMPEZA_GERAL,
        "nome": NOME_LIMPEZA_GERAL,
        "rotulo": "Limpeza geral",
        "posicao": "fim",
        "ordem": 2,
    },
)
ORIGENS_ETAPAS_FIXAS = {item["chave"] for item in ETAPAS_ORCAMENTO_FIXAS}
NOMES_ETAPAS_FIXAS = {item["chave"]: item["nome"] for item in ETAPAS_ORCAMENTO_FIXAS}

TITULO_ANOMALIA = "anomalia"
TITULO_REPARO = "reparo"
TITULO_ANOMALIA_REPARO = "anomalia_reparo"
TITULO_ETAPA = "etapa"
TITULO_PERSONALIZADO = "personalizado"

ROTULOS_TITULO_ORCAMENTO = (
    (TITULO_ANOMALIA, "Nome da anomalia"),
    (TITULO_REPARO, "Nome do reparo"),
    (TITULO_ANOMALIA_REPARO, "Anomalia — reparo"),
    (TITULO_ETAPA, "Nome da etapa pré-definida"),
    (TITULO_PERSONALIZADO, "Texto personalizado"),
)

CHAVES_TITULO_ORCAMENTO = tuple(chave for chave, _rotulo in ROTULOS_TITULO_ORCAMENTO)
CHAVES_PERCENTUAIS_ABA1 = tuple(item[0] for item in PERCENTUAIS_MODELO)
ROTULOS_PERCENTUAIS_ABA1 = {item[0]: item[1] for item in PERCENTUAIS_MODELO}
QTD_PERCENTUAIS_ABA1 = {item[0]: (item[3], item[4]) for item in PERCENTUAIS_MODELO}

TIPOS_CALCULO = (
    "area_fachada_bloco",
    "area_fachada_total",
    "area_alvenaria_hall_total",
    "area_laje_hall_total",
    "area_piso_hall_total",
    "perimetro_hall_rodape_total",
    "area_cobertura_total",
    "perimetro_paredes_externas_total",
    "perimetro_paredes_externas_bloco",
    "perimetro_platibanda_total",
    "perimetro_beiral",
    "pingadeira_total",
    "esquadria_area_total",
    "janela_area_total",
    "esquadria_perimetro_total",
    "esquadria_qtd_janelas",
    "cobogo_area_total",
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
    "pct_troca_tampas_inspecao",
    "pct_troca_tampas_gordura",
    "pct_troca_calcadas",
    "qtd_aguas_telhado",
    "pe_direito",
    "por_bloco",
    "por_pavimento",
    "pavimentos_friso",
    "por_apartamento",
    "variavel",
    "fixo",
)

ROTULOS_TIPO_CALCULO = {
    "area_fachada_bloco": "Área de fachada (um bloco, sem esquadrias)",
    "area_fachada_total": "Área de fachada (total, sem esquadrias)",
    "area_alvenaria_hall_total": "Área de alvenaria do hall (total)",
    "area_laje_hall_total": "Área da laje do hall (total)",
    "area_piso_hall_total": "Área de piso do hall (total)",
    "perimetro_hall_rodape_total": "Perímetro de rodapé do hall (total)",
    "area_cobertura_total": "Área de cobertura (total)",
    "perimetro_paredes_externas_total": "Perímetro de paredes externas (total)",
    "perimetro_paredes_externas_bloco": "Perímetro de paredes externas (um bloco)",
    "perimetro_platibanda_total": "Perímetro de platibanda (total)",
    "perimetro_beiral": "Perímetro de beiral (calha)",
    "pingadeira_total": "Pingadeira (total)",
    "esquadria_area_total": "Área de esquadrias (total)",
    "janela_area_total": "Área de janelas (total)",
    "esquadria_perimetro_total": "Perímetro das janelas",
    "esquadria_qtd_janelas": "Quantidade de janelas",
    "cobogo_area_total": "Área dos cobogós (total)",
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
    "pct_troca_tampas_inspecao": "% Troca de tampas das caixas de inspeção",
    "pct_troca_tampas_gordura": "% Troca de tampas das caixas de gordura",
    "pct_troca_calcadas": "% Troca de calçadas e caminhos",
    "qtd_aguas_telhado": "Quantidade de águas do telhado",
    "pe_direito": "Pé-direito",
    "por_bloco": "Por bloco",
    "por_pavimento": "Por pavimento",
    "pavimentos_friso": "Pavimentos − 1",
    "por_apartamento": "Por apartamento",
    "variavel": "Variável",
    "fixo": "Quantidade fixa",
}

ROTULOS_CURTOS_TIPO_CALCULO = {
    "area_fachada_bloco": "fachada/bloco",
    "area_fachada_total": "fachada total",
    "area_alvenaria_hall_total": "alvenaria hall",
    "area_laje_hall_total": "laje hall",
    "area_piso_hall_total": "piso hall",
    "perimetro_hall_rodape_total": "rodapé hall",
    "area_cobertura_total": "cobertura",
    "perimetro_paredes_externas_total": "perím. paredes",
    "perimetro_paredes_externas_bloco": "perím./bloco",
    "perimetro_platibanda_total": "platibanda",
    "perimetro_beiral": "beiral",
    "pingadeira_total": "pingadeira",
    "esquadria_area_total": "esquadrias",
    "janela_area_total": "área janelas",
    "esquadria_perimetro_total": "perím. janelas",
    "esquadria_qtd_janelas": "janelas",
    "cobogo_area_total": "cobogós",
    "pct_troca_revestimento_fachada": "% revest. fachada",
    "pct_troca_revestimento_paredes_hall": "% revest. paredes",
    "pct_troca_revestimento_tetos_hall": "% revest. tetos",
    "pct_troca_pisos_hall": "% pisos hall",
    "pct_troca_rodape_hall": "% rodapé",
    "pct_troca_estrutura_cobertura": "% estrutura cob.",
    "pct_instalacao_tabeira_beiral": "% tabeira",
    "pct_troca_telhas_cobertura": "% telhas",
    "pct_troca_rufos_pingadeira": "% rufos",
    "pct_pintura_fachada": "% pintura fachada",
    "pct_pintura_paredes_hall": "% pintura paredes",
    "pct_pintura_teto_hall": "% pintura teto",
    "pct_troca_tampas_inspecao": "% tampas inspeção",
    "pct_troca_tampas_gordura": "% tampas gordura",
    "pct_troca_calcadas": "% calçadas",
    "qtd_aguas_telhado": "águas",
    "pe_direito": "pé-direito",
    "por_bloco": "blocos",
    "por_pavimento": "pavimentos",
    "pavimentos_friso": "pavimentos−1",
    "por_apartamento": "apartamentos",
    "variavel": "variável",
    "fixo": "fixo",
}

MAPA_TIPO_QUANTITATIVO = {
    "area_fachada_bloco": "area_fachada_bloco_m2",
    "area_fachada_total": "area_fachada_total_m2",
    "area_alvenaria_hall_total": "area_alvenaria_hall_total_m2",
    "area_laje_hall_total": "area_laje_hall_total_m2",
    "area_piso_hall_total": "area_piso_hall_total_m2",
    "perimetro_hall_rodape_total": "perimetro_hall_rodape_total_m",
    "area_cobertura_total": "area_cobertura_total_m2",
    "perimetro_paredes_externas_total": "perimetro_paredes_externas_total_m",
    "perimetro_paredes_externas_bloco": "perimetro_paredes_externas_bloco_m",
    "perimetro_platibanda_total": "perimetro_platibanda_total_m",
    "perimetro_beiral": "perimetro_beiral_m",
    "pingadeira_total": "pingadeira_total_m",
    "esquadria_area_total": "esquadria_area_total_m2",
    "janela_area_total": "janela_area_total_m2",
    "esquadria_perimetro_total": "esquadria_perimetro_total_m",
    "esquadria_qtd_janelas": "esquadria_qtd_janelas_total",
    "cobogo_area_total": "cobogo_area_total_m2",
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
    "pct_troca_tampas_inspecao": "pct_troca_tampas_inspecao_un",
    "pct_troca_tampas_gordura": "pct_troca_tampas_gordura_un",
    "pct_troca_calcadas": "pct_troca_calcadas_m2",
    "qtd_aguas_telhado": "qtd_aguas_telhado",
    "pe_direito": "pe_direito_m",
    "por_bloco": "qtd_blocos",
    "por_pavimento": "qtd_pavimentos",
    "pavimentos_friso": "pavimentos_friso",
    "por_apartamento": "qtd_aptos_total",
}

UNIDADES_COMUNS = ("m²", "m", "m³", "H", "Un", "un", "KG", "L")


def meta_etapa_fixa(chave: str) -> dict[str, Any] | None:
    for item in ETAPAS_ORCAMENTO_FIXAS:
        if item["chave"] == chave:
            return item
    return None


def nova_etapa_orcamento_fixa(chave: str) -> dict[str, Any]:
    meta = meta_etapa_fixa(chave)
    nome = (meta or {}).get("nome") or NOMES_ETAPAS_FIXAS.get(chave) or chave
    return {"nome": nome, "itens": []}


def novos_servicos_preliminares() -> dict[str, Any]:
    return nova_etapa_orcamento_fixa(CHAVE_SERVICOS_PRELIMINARES)


def catalogo_vazio() -> dict[str, Any]:
    base = {
        "versao": VERSAO_CATALOGO,
        "anomalias": {},
    }
    for meta in ETAPAS_ORCAMENTO_FIXAS:
        base[meta["chave"]] = nova_etapa_orcamento_fixa(meta["chave"])
    return base


def _coeficiente_item(coeficiente) -> float:
    try:
        if isinstance(coeficiente, str):
            texto = coeficiente.strip()
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            return float(texto)
        return float(coeficiente)
    except (TypeError, ValueError):
        return 1.0


OPERACAO_MULTIPLICAR = "multiplicar"
OPERACAO_SOMAR = "somar"


def novo_fator(
    *,
    tipo_calculo: str = "fixo",
    coeficiente: float = 1.0,
    operacao: str = OPERACAO_MULTIPLICAR,
    pergunta: str = "",
) -> dict[str, Any]:
    tipo = str(tipo_calculo or "fixo")
    junta = str(operacao or OPERACAO_MULTIPLICAR)
    if junta not in (OPERACAO_MULTIPLICAR, OPERACAO_SOMAR):
        junta = OPERACAO_MULTIPLICAR
    fator = {
        "tipo_calculo": tipo if tipo in TIPOS_CALCULO else "fixo",
        "coeficiente": _coeficiente_item(coeficiente),
        "operacao": junta,
    }
    if fator["tipo_calculo"] == "variavel":
        fator["pergunta"] = str(pergunta or "").strip()
    return fator


def normalizar_fatores(bruto) -> list[dict[str, Any]]:
    """Aceita lista `fatores` ou o par legado tipo_calculo/coeficiente."""
    if isinstance(bruto, dict):
        origem = bruto.get("fatores")
        if isinstance(origem, list) and origem:
            fatores = []
            for item in origem:
                if not isinstance(item, dict):
                    continue
                fatores.append(
                    novo_fator(
                        tipo_calculo=item.get("tipo_calculo") or "fixo",
                        coeficiente=item.get("coeficiente", 1),
                        operacao=item.get("operacao") or OPERACAO_MULTIPLICAR,
                        pergunta=item.get("pergunta") or "",
                    )
                )
            if fatores:
                fatores[0]["operacao"] = OPERACAO_MULTIPLICAR
                return fatores
        return [
            novo_fator(
                tipo_calculo=bruto.get("tipo_calculo") or "fixo",
                coeficiente=bruto.get("coeficiente", 1),
            )
        ]
    if isinstance(bruto, list) and bruto:
        fatores = []
        for item in bruto:
            if not isinstance(item, dict):
                continue
            fatores.append(
                novo_fator(
                    tipo_calculo=item.get("tipo_calculo") or "fixo",
                    coeficiente=item.get("coeficiente", 1),
                    operacao=item.get("operacao") or OPERACAO_MULTIPLICAR,
                    pergunta=item.get("pergunta") or "",
                )
            )
        if fatores:
            fatores[0]["operacao"] = OPERACAO_MULTIPLICAR
            return fatores
    return [novo_fator()]


def _aplicar_fatores_no_item(item: dict[str, Any], fatores: list[dict[str, Any]]) -> dict[str, Any]:
    fatores = normalizar_fatores(fatores)
    item["fatores"] = fatores
    # Campos legados: primeiro fator (compatível com catálogos/UI antigos).
    item["tipo_calculo"] = fatores[0]["tipo_calculo"]
    item["coeficiente"] = fatores[0]["coeficiente"]
    return item


def _multiplicador_item(valor) -> float:
    try:
        numero = float(valor if valor not in (None, "") else 1)
    except (TypeError, ValueError):
        return 1.0
    return numero


def _letra_tipo_sinapi(valor) -> str:
    letra = str(valor or "").strip().upper()[:1]
    return letra if letra in ("I", "C") else ""


def rotulo_tipo_item_catalogo(item, sinapi=None) -> str:
    """Rótulo da coluna Tipo: composição própria ou SINAPI insumo/composição."""
    dados = item or {}
    if str(dados.get("tipo") or "") == TIPO_ITEM_CATALOGO_PROPRIA:
        return "Composição própria"
    letra = _letra_tipo_sinapi(dados.get("tipo_sinapi"))
    if not letra and sinapi is not None:
        codigo = dados.get("codigo_sinapi") or dados.get("codigo") or ""
        try:
            letra = _letra_tipo_sinapi(sinapi.obter_tipo(str(codigo)))
        except (AttributeError, TypeError, ValueError):
            letra = ""
    if letra == "I":
        return "SINAPI · Insumo"
    if letra == "C":
        return "SINAPI · Composição"
    return "SINAPI"


def novo_item_sinapi(
    *,
    codigo_sinapi: str = "",
    unidade: str = "m²",
    tipo_calculo: str = "area_fachada_total",
    coeficiente: float = 1.0,
    fatores: list | None = None,
    da_etapa: bool = False,
    multiplicador: float = 1.0,
    tipo_sinapi: str = "",
) -> dict[str, Any]:
    item = {
        "id": novo_id(),
        "tipo": TIPO_ITEM_CATALOGO_SINAPI,
        "codigo_sinapi": str(codigo_sinapi).strip(),
        "unidade": str(unidade or "m²").strip(),
        "da_etapa": bool(da_etapa),
        "multiplicador": _multiplicador_item(multiplicador),
        "tipo_sinapi": _letra_tipo_sinapi(tipo_sinapi),
    }
    return _aplicar_fatores_no_item(
        item,
        fatores
        if fatores is not None
        else [novo_fator(tipo_calculo=tipo_calculo, coeficiente=coeficiente)],
    )


def novo_item_composicao_propria(
    *,
    composicao_catalogo_id: str = "",
    codigo: str = "",
    nome: str = "",
    unidade: str = "un",
    tipo_calculo: str = "fixo",
    coeficiente: float = 1.0,
    fatores: list | None = None,
    da_etapa: bool = False,
    multiplicador: float = 1.0,
) -> dict[str, Any]:
    item = {
        "id": novo_id(),
        "tipo": TIPO_ITEM_CATALOGO_PROPRIA,
        "composicao_catalogo_id": str(composicao_catalogo_id or "").strip(),
        "codigo": str(codigo or "").strip(),
        "nome": str(nome or "").strip(),
        "unidade": str(unidade or "un").strip(),
        "da_etapa": bool(da_etapa),
        "multiplicador": _multiplicador_item(multiplicador),
    }
    return _aplicar_fatores_no_item(
        item,
        fatores
        if fatores is not None
        else [novo_fator(tipo_calculo=tipo_calculo, coeficiente=coeficiente)],
    )


def _definir_fundo_selador(item: dict, valor) -> dict:
    """Grava a marca só quando é fundo selador. A ausência vale como falso."""
    if valor:
        item["fundo_selador"] = True
    else:
        item.pop("fundo_selador", None)
    return item


def _normalizar_item_catalogo(bruto: dict) -> dict[str, Any] | None:
    if not isinstance(bruto, dict):
        return None
    tipo = str(bruto.get("tipo") or "").strip()
    if not tipo:
        if bruto.get("composicao_catalogo_id") or (
            bruto.get("codigo") and not bruto.get("codigo_sinapi")
        ):
            tipo = TIPO_ITEM_CATALOGO_PROPRIA
        else:
            tipo = TIPO_ITEM_CATALOGO_SINAPI
    fatores = normalizar_fatores(bruto)
    if tipo == TIPO_ITEM_CATALOGO_PROPRIA:
        novo = novo_item_composicao_propria(
            composicao_catalogo_id=bruto.get("composicao_catalogo_id"),
            codigo=bruto.get("codigo"),
            nome=bruto.get("nome") or bruto.get("descricao"),
            unidade=bruto.get("unidade") or "un",
            fatores=fatores,
            da_etapa=bool(bruto.get("da_etapa")),
            multiplicador=bruto.get("multiplicador", 1),
        )
    else:
        novo = novo_item_sinapi(
            codigo_sinapi=bruto.get("codigo_sinapi") or bruto.get("codigo"),
            unidade=bruto.get("unidade") or "m²",
            fatores=fatores,
            da_etapa=bool(bruto.get("da_etapa")),
            multiplicador=bruto.get("multiplicador", 1),
            tipo_sinapi=bruto.get("tipo_sinapi", ""),
        )
    if bruto.get("id"):
        novo["id"] = str(bruto.get("id"))
    _definir_fundo_selador(novo, bruto.get("fundo_selador"))
    return novo


def normalizar_etapa_orcamento_fixa(bruto, chave: str) -> dict[str, Any]:
    base = nova_etapa_orcamento_fixa(chave)
    if not isinstance(bruto, dict):
        return base
    nome = str(bruto.get("nome") or "").strip()
    if nome:
        base["nome"] = nome
    itens = []
    for item in bruto.get("itens") or []:
        normalizado = _normalizar_item_catalogo(item)
        if normalizado is not None:
            itens.append(normalizado)
    base["itens"] = itens
    return base


def normalizar_servicos_preliminares(bruto) -> dict[str, Any]:
    return normalizar_etapa_orcamento_fixa(bruto, CHAVE_SERVICOS_PRELIMINARES)


def itens_servicos_da_etapa(
    etapa: dict | None,
    itens_atuais: list | None = None,
    *,
    tipo_calculo_padrao: str = "fixo",
) -> list[dict[str, Any]]:
    """Copia SINAPI e composições próprias da etapa, preservando cálculo já definido."""
    padrao = tipo_calculo_padrao if tipo_calculo_padrao in TIPOS_CALCULO else "fixo"
    atuais = [i for i in (itens_atuais or []) if isinstance(i, dict)]
    novos: list[dict[str, Any]] = []
    usados_ids: set[str] = set()

    def _achar_anterior(chave: tuple) -> dict | None:
        for item in atuais:
            tipo = str(item.get("tipo") or TIPO_ITEM_CATALOGO_SINAPI)
            if tipo == TIPO_ITEM_CATALOGO_PROPRIA:
                marca = (
                    "P",
                    str(item.get("composicao_catalogo_id") or ""),
                    str(item.get("codigo") or ""),
                )
            else:
                marca = ("S", str(item.get("codigo_sinapi") or item.get("codigo") or ""), "")
            if marca == chave:
                return item
        return None

    for ref in (etapa or {}).get("itens") or []:
        if not isinstance(ref, dict):
            continue
        tipo = str(ref.get("tipo") or "")
        if tipo == TIPO_ITEM_SINAPI:
            codigo = str(ref.get("codigo") or "").strip()
            if not codigo:
                continue
            anterior = _achar_anterior(("S", codigo, ""))
            fatores = (
                normalizar_fatores(anterior)
                if anterior
                else [novo_fator(tipo_calculo=padrao, coeficiente=1)]
            )
            novo = novo_item_sinapi(
                codigo_sinapi=codigo,
                unidade=(anterior or {}).get("unidade") or ref.get("unidade") or "un",
                fatores=fatores,
                da_etapa=True,
                multiplicador=(anterior or {}).get("multiplicador", 1),
                tipo_sinapi=(anterior or {}).get("tipo_sinapi")
                or ref.get("tipo_sinapi")
                or "",
            )
            if anterior and anterior.get("id"):
                novo["id"] = str(anterior.get("id"))
                usados_ids.add(novo["id"])
            _definir_fundo_selador(novo, (anterior or {}).get("fundo_selador"))
            novos.append(novo)
        elif tipo == TIPO_ITEM_PROPRIA:
            catalogo_id = str(ref.get("composicao_catalogo_id") or "").strip()
            codigo = str(ref.get("codigo") or "").strip()
            anterior = _achar_anterior(("P", catalogo_id, codigo))
            fatores = (
                normalizar_fatores(anterior)
                if anterior
                else [novo_fator(tipo_calculo=padrao, coeficiente=1)]
            )
            novo = novo_item_composicao_propria(
                composicao_catalogo_id=catalogo_id,
                codigo=codigo,
                nome=(anterior or {}).get("nome") or ref.get("nome") or codigo,
                unidade=(anterior or {}).get("unidade") or ref.get("unidade") or "un",
                fatores=fatores,
                da_etapa=True,
                multiplicador=(anterior or {}).get("multiplicador", 1),
            )
            if anterior and anterior.get("id"):
                novo["id"] = str(anterior.get("id"))
                usados_ids.add(novo["id"])
            _definir_fundo_selador(novo, (anterior or {}).get("fundo_selador"))
            novos.append(novo)

    for item in atuais:
        ident = str(item.get("id") or "")
        if ident and ident in usados_ids:
            continue
        if item.get("da_etapa"):
            continue
        extra = _normalizar_item_catalogo(deepcopy(item)) or deepcopy(item)
        if not extra.get("tipo"):
            extra["tipo"] = TIPO_ITEM_CATALOGO_SINAPI
        novos.append(extra)
    return novos


def novo_reparo(*, nome: str = "Reparo padrão", origem: str = ORIGEM_ITENS) -> dict[str, Any]:
    return {
        "id": novo_id(),
        "nome": str(nome or "Reparo padrão").strip(),
        "origem": origem if origem in (ORIGEM_ITENS, ORIGEM_ETAPA) else ORIGEM_ITENS,
        "etapa_predefinida_id": "",
        "etapa_nome": "",
        "tipo_calculo_etapa": "fixo",
        "titulo_orcamento": TITULO_ANOMALIA_REPARO,
        "titulo_personalizado": "",
        "percentuais_aba1": [],
        "itens": [],
    }


def recomendacao_vazia() -> dict[str, Any]:
    return {"criterio": CRITERIO_NENHUM, "por_opcao": {}}


def opcoes_do_criterio(criterio: str) -> tuple[str, ...]:
    if criterio == CRITERIO_ESTRUTURA:
        return TIPOS_ESTRUTURA
    if criterio == CRITERIO_COBERTURA:
        return TIPOS_COBERTURA
    return ()


def normalizar_recomendacao(bruto, reparos) -> dict[str, Any]:
    ids = {
        str(reparo.get("id") or "")
        for reparo in reparos or []
        if isinstance(reparo, dict) and reparo.get("id")
    }
    criterio = CRITERIO_NENHUM
    por_bruto: dict = {}
    if isinstance(bruto, dict):
        candidato = str(bruto.get("criterio") or "")
        if candidato in (CRITERIO_ESTRUTURA, CRITERIO_COBERTURA):
            criterio = candidato
        origem = bruto.get("por_opcao")
        if isinstance(origem, dict):
            por_bruto = origem
    por_opcao = {}
    for opcao in opcoes_do_criterio(criterio):
        reparo_id = str(por_bruto.get(opcao) or "")
        if reparo_id in ids:
            por_opcao[opcao] = reparo_id
    return {"criterio": criterio, "por_opcao": por_opcao}


def reparo_recomendado(
    anomalia: dict | None,
    *,
    tipo_estrutura: str = "",
    tipo_cobertura: str = "",
) -> tuple[dict | None, str]:
    """Reparo sugerido e o texto da dica. Sem critério, a dica fica vazia."""
    if not isinstance(anomalia, dict):
        return None, ""
    rec = normalizar_recomendacao(
        anomalia.get("recomendacao"), anomalia.get("reparos") or []
    )
    criterio = rec.get("criterio") or CRITERIO_NENHUM
    if criterio == CRITERIO_ESTRUTURA:
        campo = "Tipo de estrutura"
        valor = str(tipo_estrutura or "").strip()
    elif criterio == CRITERIO_COBERTURA:
        campo = "Tipo de cobertura"
        valor = str(tipo_cobertura or "").strip()
    else:
        return None, ""
    if not valor:
        return None, f"Defina o {campo} na aba 1 para indicar o reparo recomendado."
    reparo_id = str((rec.get("por_opcao") or {}).get(valor) or "")
    reparos = [r for r in (anomalia.get("reparos") or []) if isinstance(r, dict)]
    reparo = next(
        (item for item in reparos if str(item.get("id") or "") == reparo_id),
        None,
    )
    if reparo is None:
        return None, f"Não há reparo recomendado para {valor}."
    nome = str(reparo.get("nome") or "Reparo").strip() or "Reparo"
    return reparo, f"Reparo recomendado para {valor}: {nome}."


def nova_anomalia(nome: str) -> dict[str, Any]:
    return {
        "reparos": [novo_reparo(nome="Reparo padrão")],
        "recomendacao": recomendacao_vazia(),
    }


def semear_etapas_orcamento_fixas(catalogo: dict[str, Any]) -> bool:
    """Preenche etapas fixas vazias a partir das etapas pré-definidas. Retorna se alterou."""
    if not isinstance(catalogo, dict):
        return False

    vazias: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for meta in ETAPAS_ORCAMENTO_FIXAS:
        chave = meta["chave"]
        etapa = normalizar_etapa_orcamento_fixa(catalogo.get(chave), chave)
        catalogo[chave] = etapa
        if not etapa.get("itens"):
            vazias.append((meta, etapa))
    if not vazias:
        return False

    try:
        from core.etapas_predefinidas_storage import (
            carregar,
            listar,
            obter_cache_catalogo,
        )

        if obter_cache_catalogo() is None:
            carregar()
        etapas = listar()
    except (ValueError, OSError, TypeError, ImportError):
        return False

    por_nome = {
        str(item.get("nome") or "").strip().casefold(): item for item in etapas
    }
    alterou = False
    for meta, etapa in vazias:
        encontrada = por_nome.get(str(meta.get("nome") or "").casefold())
        if encontrada is None:
            continue
        etapa["itens"] = itens_servicos_da_etapa(
            encontrada, tipo_calculo_padrao="fixo"
        )
        if not (etapa.get("nome") or "").strip():
            etapa["nome"] = encontrada.get("nome") or meta["nome"]
        catalogo[meta["chave"]] = etapa
        alterou = True
    return alterou


def carregar_catalogo(caminho: Path | None = None) -> dict[str, Any]:
    origem = caminho or anomalias_area_comum_path()
    if not Path(origem).is_file():
        dados = catalogo_vazio()
    else:
        try:
            with open(origem, "r", encoding="utf-8") as f:
                bruto = json.load(f)
        except (OSError, json.JSONDecodeError):
            dados = catalogo_vazio()
        else:
            dados = normalizar_catalogo(bruto)
    semear_etapas_orcamento_fixas(dados)
    return dados


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
    for meta in ETAPAS_ORCAMENTO_FIXAS:
        chave = meta["chave"]
        base[chave] = normalizar_etapa_orcamento_fixa(dados.get(chave), chave)
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
                item
                for item in (
                    _normalizar_item_catalogo(etapa)
                    for etapa in bruto.get("etapas") or []
                    if isinstance(etapa, dict)
                )
                if item is not None
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
                fonte_titulo = str(item.get("titulo_orcamento") or TITULO_ANOMALIA_REPARO)
                reparo["titulo_orcamento"] = (
                    fonte_titulo
                    if fonte_titulo in CHAVES_TITULO_ORCAMENTO
                    else TITULO_ANOMALIA_REPARO
                )
                reparo["titulo_personalizado"] = str(
                    item.get("titulo_personalizado") or ""
                ).strip()
                reparo["percentuais_aba1"] = percentuais_aba1_validos(
                    item.get("percentuais_aba1")
                )
                itens = []
                for etapa in item.get("itens") or []:
                    normalizado = _normalizar_item_catalogo(etapa)
                    if normalizado is not None:
                        itens.append(normalizado)
                reparo["itens"] = itens
                reparos.append(reparo)
        if not reparos:
            reparos = [novo_reparo(nome="Reparo padrão")]
        base["anomalias"][titulo] = {
            "reparos": reparos,
            "recomendacao": normalizar_recomendacao(
                bruto.get("recomendacao"), reparos
            ),
        }
    return base


def obter_etapa_orcamento_fixa(
    chave: str, dados: dict | None = None
) -> dict[str, Any]:
    origem = dados if dados is not None else carregar_catalogo()
    return deepcopy(
        normalizar_etapa_orcamento_fixa((origem or {}).get(chave), chave)
    )


def obter_servicos_preliminares(dados: dict | None = None) -> dict[str, Any]:
    return obter_etapa_orcamento_fixa(CHAVE_SERVICOS_PRELIMINARES, dados)


def _chave_ordem_alfabetica(nome: str) -> str:
    base = unicodedata.normalize("NFD", str(nome).casefold())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def nomes_anomalias(dados: dict | None = None) -> list[str]:
    origem = dados if dados is not None else carregar_catalogo()
    nomes = list((origem.get("anomalias") or {}).keys())
    return sorted(nomes, key=_chave_ordem_alfabetica)


def obter_anomalia(nome: str, dados: dict | None = None) -> dict | None:
    origem = dados if dados is not None else carregar_catalogo()
    return deepcopy((origem.get("anomalias") or {}).get(nome))


def obter_reparo(
    nome: str,
    reparo_id: str = "",
    dados: dict | None = None,
) -> dict | None:
    cadastro = obter_anomalia(nome, dados) or {}
    reparos = [r for r in (cadastro.get("reparos") or []) if isinstance(r, dict)]
    rid = str(reparo_id or "")
    if rid:
        for reparo in reparos:
            if str(reparo.get("id") or "") == rid:
                return reparo
    return reparos[0] if reparos else None


def rotulo_titulo_orcamento(chave: str) -> str:
    for ident, rotulo in ROTULOS_TITULO_ORCAMENTO:
        if ident == chave:
            return rotulo
    return dict(ROTULOS_TITULO_ORCAMENTO)[TITULO_ANOMALIA_REPARO]


def chave_titulo_orcamento(rotulo: str) -> str:
    for ident, texto in ROTULOS_TITULO_ORCAMENTO:
        if texto == rotulo or ident == rotulo:
            return ident
    return TITULO_ANOMALIA_REPARO


_QTD_PARA_PERCENTUAL_ABA1 = {
    qtd: chave for chave, (qtd, _unidade) in QTD_PERCENTUAIS_ABA1.items()
}


def percentuais_dos_fatores(reparo, etapas_por_id=None) -> list[str]:
    """Percentuais da aba 1 usados na fórmula do reparo, na ordem da aba."""
    usadas: set[str] = set()
    for item in itens_efetivos_reparo(reparo, etapas_por_id):
        for fator in normalizar_fatores(item):
            qtd = MAPA_TIPO_QUANTITATIVO.get(str(fator.get("tipo_calculo") or ""))
            chave = _QTD_PARA_PERCENTUAL_ABA1.get(qtd or "")
            if chave:
                usadas.add(chave)
    return [chave for chave in CHAVES_PERCENTUAIS_ABA1 if chave in usadas]


def percentuais_aba1_validos(valores) -> list[str]:
    if not isinstance(valores, (list, tuple)):
        return []
    vistos = set()
    resultado = []
    conhecidas = set(CHAVES_PERCENTUAIS_ABA1)
    for chave in valores:
        ident = str(chave or "").strip()
        if ident not in conhecidas or ident in vistos:
            continue
        vistos.add(ident)
        resultado.append(ident)
    return resultado


def titulo_grupo_orcamento(anomalia: dict, reparo: dict | None = None) -> str:
    reparo = reparo or {}
    fonte = str(reparo.get("titulo_orcamento") or TITULO_ANOMALIA_REPARO)
    if fonte not in CHAVES_TITULO_ORCAMENTO:
        fonte = TITULO_ANOMALIA_REPARO
    nome = str(anomalia.get("nome") or "").strip()
    reparo_nome = str(
        anomalia.get("reparo_nome") or reparo.get("nome") or ""
    ).strip()
    etapa_nome = str(reparo.get("etapa_nome") or "").strip()
    personalizado = str(reparo.get("titulo_personalizado") or "").strip()
    if fonte == TITULO_REPARO:
        return reparo_nome or nome
    if fonte == TITULO_ETAPA:
        return etapa_nome or nome
    if fonte == TITULO_PERSONALIZADO:
        return personalizado or nome
    if fonte == TITULO_ANOMALIA:
        return nome
    if reparo_nome and reparo_nome != "Reparo padrão":
        return f"{nome} — {reparo_nome}" if nome else reparo_nome
    return nome


def itens_sinapi_da_etapa(
    etapa: dict | None,
    itens_atuais: list | None = None,
    *,
    tipo_calculo_padrao: str = "fixo",
) -> list[dict[str, Any]]:
    """Copia SINAPI e composições próprias da etapa, preservando o cálculo já definido."""
    return itens_servicos_da_etapa(
        etapa,
        itens_atuais,
        tipo_calculo_padrao=tipo_calculo_padrao,
    )


def itens_efetivos_reparo(
    reparo: dict | None,
    etapas_por_id: dict | None = None,
) -> list[dict[str, Any]]:
    reparo = reparo or {}
    itens = [i for i in (reparo.get("itens") or []) if isinstance(i, dict)]
    if itens:
        return itens
    if (reparo.get("origem") or ORIGEM_ITENS) != ORIGEM_ETAPA:
        return []
    etapa_id = str(reparo.get("etapa_predefinida_id") or "")
    etapa = (etapas_por_id or {}).get(etapa_id)
    if not etapa:
        return []
    return itens_sinapi_da_etapa(
        etapa,
        tipo_calculo_padrao=reparo.get("tipo_calculo_etapa") or "fixo",
    )


def fator_percentual_anomalia(percentual) -> float:
    valor = numero(percentual if percentual not in (None, "") else "100", percentual=True)
    if valor < 0:
        return 0.0
    return valor / 100.0


_TIPO_REVESTIMENTO_FACHADA = "pct_troca_revestimento_fachada"
_TIPOS_FAIXA_FACHADA = frozenset(
    {
        "perimetro_paredes_externas_total",
        "por_bloco",
    }
)


def _unidade_area(item) -> bool:
    texto = str((item or {}).get("unidade") or "").strip().casefold().replace("²", "2")
    return texto in {"m2"}


def _e_faixa_sobre_fachada(item) -> bool:
    """Área já executada na fachada: faixa do perímetro ou quantidade por bloco, em m²."""
    tipos = _tipos_fator(item) - {"fixo"}
    return bool(tipos) and tipos <= _TIPOS_FAIXA_FACHADA and _unidade_area(item)


def _codigo_item_catalogo(item) -> str:
    return str((item or {}).get("codigo_sinapi") or (item or {}).get("codigo") or "").strip()


def _tipos_fator(item) -> set[str]:
    return {
        str(fator.get("tipo_calculo") or "")
        for fator in normalizar_fatores(item)
    }


def _quantidade_efetiva(item, quantitativos, variaveis, percentual) -> float:
    return quantidade_de_item(item, quantitativos, variaveis) * fator_percentual_anomalia(
        percentual
    )


def _metros_do_fator(item, tipo, quantitativos) -> float:
    total = 0.0
    for fator in normalizar_fatores(item):
        if str(fator.get("tipo_calculo") or "") != tipo:
            continue
        total += quantidade_item(tipo, fator.get("coeficiente") or 1, quantitativos or {})
    return total


def _item_com_fator_escalado(item, tipo, razao) -> dict:
    ajustado = deepcopy(item)
    fatores = []
    for fator in normalizar_fatores(ajustado):
        fator = dict(fator)
        if str(fator.get("tipo_calculo") or "") == tipo:
            fator["coeficiente"] = _coeficiente_item(fator.get("coeficiente") or 1) * razao
        fatores.append(fator)
    return _aplicar_fatores_no_item(ajustado, fatores)


def limitar_revestimento_fachada(
    anomalias,
    catalogo,
    quantitativos,
    etapas_por_id=None,
) -> tuple[dict[str, dict[str, float]], dict[str, tuple[str, ...]]]:
    """Corta o reboco da fachada só quando a soma passa da área total.

    A faixa do perímetro e a área por bloco, em m², ocupam a fachada quando
    repetem alguma composição do reboco. Essa área vale para todas as camadas
    do mesmo revestimento: demolição, chapisco e emboço cobrem os mesmos metros.
    Camadas da mesma anomalia não se somam; usa-se a maior. Itens de hall ficam inteiros.
    """
    quantitativos = quantitativos or {}
    teto = float(quantitativos.get("area_fachada_total_m2") or 0)
    doadores: dict[str, dict] = {}
    fachadas: dict[str, list[dict]] = {}
    for linha in anomalias or []:
        if not isinstance(linha, dict):
            continue
        nome = str(linha.get("nome") or "").strip()
        if not nome:
            continue
        reparo = obter_reparo(nome, linha.get("reparo_id") or "", catalogo)
        if not reparo:
            continue
        percentual = linha.get("percentual")
        variaveis = linha.get("variaveis")
        ident = str(linha.get("id") or "")
        for indice, item in enumerate(itens_efetivos_reparo(reparo, etapas_por_id)):
            codigo = _codigo_item_catalogo(item)
            if not codigo:
                continue
            tipos = _tipos_fator(item)
            item_id = str(item.get("id") or f"{codigo}#{indice}")
            if _e_faixa_sobre_fachada(item):
                faixa = max(
                    0.0,
                    _quantidade_efetiva(item, quantitativos, variaveis, percentual),
                )
                reg = doadores.setdefault(ident, {"nome": nome, "areas": {}})
                reg["areas"][codigo] = reg["areas"].get(codigo, 0.0) + faixa
                continue
            if _TIPO_REVESTIMENTO_FACHADA not in tipos:
                continue
            reivindicado = _metros_do_fator(
                item, _TIPO_REVESTIMENTO_FACHADA, quantitativos
            )
            reivindicado *= fator_percentual_anomalia(percentual)
            fachadas.setdefault(codigo, []).append(
                {
                    "anomalia_id": ident,
                    "item_id": item_id,
                    "item": item,
                    "percentual": percentual,
                    "variaveis": variaveis,
                    "reivindicado": max(0.0, reivindicado),
                }
            )

    codigos_receptor = set(fachadas)
    ocupada = 0.0
    origens: set[str] = set()
    for reg in doadores.values():
        relevantes = [
            qtd
            for cod, qtd in reg["areas"].items()
            if cod in codigos_receptor and qtd > 0
        ]
        if not relevantes:
            continue
        ocupada += max(relevantes)
        origens.add(reg["nome"])

    ajustes: dict[str, dict[str, float]] = {}
    avisos: dict[str, set[str]] = {}
    if ocupada <= 1e-9 or not origens:
        return ajustes, {}
    for _codigo, pedidos in fachadas.items():
        restante = teto - ocupada
        for pedido in pedidos:
            reivindicado = pedido["reivindicado"]
            if reivindicado <= restante + 1e-9:
                restante -= reivindicado
                continue
            mantido = max(0.0, restante)
            restante = 0.0
            razao = 0.0 if reivindicado <= 1e-12 else mantido / reivindicado
            ajustado = _item_com_fator_escalado(
                pedido["item"], _TIPO_REVESTIMENTO_FACHADA, razao
            )
            qtd = _quantidade_efetiva(
                ajustado,
                quantitativos,
                pedido["variaveis"],
                pedido["percentual"],
            )
            ajustes.setdefault(pedido["anomalia_id"], {})[pedido["item_id"]] = qtd
            avisos.setdefault(pedido["anomalia_id"], set()).update(origens)
    return ajustes, {
        chave: tuple(sorted(nomes)) for chave, nomes in avisos.items() if nomes
    }


def valores_considerados_reparo(
    reparo: dict | None,
    quantitativos: dict | None,
    percentual,
    etapas_por_id: dict | None = None,
    variaveis=None,
    quantidades_por_id=None,
) -> list[tuple[float, str]]:
    """Quantidades efetivas do reparo (únicas por fórmula/unidade)."""
    reparo = reparo or {}
    quantitativos = quantitativos or {}
    fator = fator_percentual_anomalia(percentual)
    resultado: list[tuple[float, str]] = []
    vistos: set[tuple] = set()
    for indice, item in enumerate(itens_efetivos_reparo(reparo, etapas_por_id)):
        fatores = normalizar_fatores(item)
        item_id = str(item.get("id") or f"{_codigo_item_catalogo(item)}#{indice}")
        if quantidades_por_id and item_id in quantidades_por_id:
            qtd = float(quantidades_por_id[item_id])
        else:
            qtd = quantidade_de_item(item, quantitativos, variaveis) * fator
        unid = str(item.get("unidade") or "").strip() or "un"
        marca = (
            tuple(
                (
                    f["tipo_calculo"],
                    round(float(f["coeficiente"]), 6),
                    f.get("operacao") or OPERACAO_MULTIPLICAR,
                    _chave_pergunta(f.get("pergunta")),
                )
                for f in fatores
            ),
            unid,
            round(float(qtd), 4),
        )
        if marca in vistos:
            continue
        vistos.add(marca)
        resultado.append((qtd, unid))
    if resultado:
        return resultado
    for chave in percentuais_aba1_validos(reparo.get("percentuais_aba1")):
        modelo = QTD_PERCENTUAIS_ABA1.get(chave)
        if not modelo:
            continue
        qtd_chave, unidade = modelo
        if qtd_chave in vistos:
            continue
        vistos.add(qtd_chave)
        resultado.append((float(quantitativos.get(qtd_chave) or 0), unidade))
    return resultado


def ajustar_demaos_fundo_selador(itens, *, duas_demaos: bool = True) -> list:
    """Com uma demão, o coeficiente 2 dos itens marcados como fundo selador vira 1."""
    origem = list(itens or [])
    if duas_demaos:
        return origem
    saida = []
    for item in origem:
        if not isinstance(item, dict):
            saida.append(item)
            continue
        if not item.get("fundo_selador"):
            saida.append(item)
            continue
        copia = deepcopy(item)
        fatores = normalizar_fatores(copia)
        for fator in fatores:
            coef = _coeficiente_item(fator.get("coeficiente") or 0)
            if abs(coef - 2.0) < 1e-9:
                fator["coeficiente"] = 1.0
        _aplicar_fatores_no_item(copia, fatores)
        saida.append(copia)
    return saida


def _texto_pergunta(fator) -> str:
    return str((fator or {}).get("pergunta") or "").strip() or "Informe o valor."


def _chave_pergunta(texto) -> str:
    return str(texto or "").strip().casefold()


def perguntas_variaveis_itens(itens) -> list[dict[str, str]]:
    """Perguntas distintas dos fatores variáveis, na ordem em que aparecem."""
    saida: list[dict[str, str]] = []
    vistas: set[str] = set()
    for item in itens or []:
        for fator in normalizar_fatores(item):
            if fator.get("tipo_calculo") != "variavel":
                continue
            pergunta = _texto_pergunta(fator)
            chave = _chave_pergunta(pergunta)
            if chave in vistas:
                continue
            vistas.add(chave)
            saida.append({"pergunta": pergunta})
    return saida


def perguntas_variaveis_reparo(
    reparo: dict | None, etapas_por_id: dict | None = None
) -> list[dict[str, str]]:
    return perguntas_variaveis_itens(itens_efetivos_reparo(reparo, etapas_por_id))


def mapa_variaveis(variaveis) -> dict[str, float]:
    mapa: dict[str, float] = {}
    for item in variaveis or []:
        if not isinstance(item, dict):
            continue
        chave = _chave_pergunta(item.get("pergunta"))
        if not chave:
            continue
        mapa[chave] = numero(item.get("valor"))
    return mapa


def quantidade_item(tipo_calculo: str, coeficiente: float, quantitativos: dict) -> float:
    coef = float(coeficiente or 0)
    if tipo_calculo == "fixo":
        return coef
    chave = MAPA_TIPO_QUANTITATIVO.get(tipo_calculo)
    if not chave:
        return coef
    base = float(quantitativos.get(chave) or 0)
    return base * coef


def quantidade_de_item(
    item: dict | None,
    quantitativos: dict | None,
    variaveis=None,
) -> float:
    """Combina os fatores com × ou +, na ordem em que foram cadastrados."""
    respostas = mapa_variaveis(variaveis)
    total = None
    for fator in normalizar_fatores(item or {}):
        tipo = fator.get("tipo_calculo") or "fixo"
        if tipo == "variavel":
            coef = _coeficiente_item(fator.get("coeficiente") or 1)
            parcela = float(respostas.get(_chave_pergunta(_texto_pergunta(fator))) or 0) * coef
        else:
            parcela = quantidade_item(
                tipo,
                fator.get("coeficiente") or 1,
                quantitativos or {},
            )
        if total is None or fator.get("operacao") != OPERACAO_SOMAR:
            total = parcela if total is None else total * parcela
        else:
            total += parcela
    if total is None:
        return 0.0
    return total * _multiplicador_item((item or {}).get("multiplicador", 1))


def _fmt_coef_curto(valor: float) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if abs(numero - round(numero)) < 1e-9:
        return str(int(round(numero)))
    texto = f"{numero:.4f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def rotulo_fatores(item_ou_fatores) -> str:
    """Resumo curto da fórmula, ex.: «perím. paredes×0,5 + piso hall»."""
    fatores = normalizar_fatores(item_ou_fatores)
    texto = ""
    for indice, fator in enumerate(fatores):
        tipo = fator.get("tipo_calculo") or "fixo"
        coef = _coeficiente_item(fator.get("coeficiente") or 1)
        if tipo == "fixo":
            parte = _fmt_coef_curto(coef)
        elif tipo == "variavel":
            pergunta = str(fator.get("pergunta") or "").strip()
            base = pergunta if pergunta else "variável"
            if len(base) > 42:
                base = base[:41].rstrip() + "…"
            parte = base if abs(coef - 1.0) < 1e-9 else f"{base}×{_fmt_coef_curto(coef)}"
        else:
            base = ROTULOS_CURTOS_TIPO_CALCULO.get(tipo) or tipo
            parte = base if abs(coef - 1.0) < 1e-9 else f"{base}×{_fmt_coef_curto(coef)}"
        if indice == 0:
            texto = parte
        elif fator.get("operacao") == OPERACAO_SOMAR:
            texto = f"{texto} + {parte}"
        else:
            texto = f"{texto} × {parte}"
    if isinstance(item_ou_fatores, dict):
        multiplicador = _multiplicador_item(item_ou_fatores.get("multiplicador", 1))
        if texto and abs(multiplicador - 1.0) > 1e-9:
            texto = f"({texto}) × {_fmt_coef_curto(multiplicador)}"
    return texto or "—"
