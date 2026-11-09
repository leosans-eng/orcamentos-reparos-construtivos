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
from core.area_comum import PERCENTUAIS_MODELO, novo_id
from core.area_comum_calculos import numero
from core.etapas_predefinidas import TIPO_ITEM_PROPRIA, TIPO_ITEM_SINAPI

VERSAO_CATALOGO = 1

ORIGEM_ITENS = "itens"
ORIGEM_ETAPA = "etapa_predefinida"
ORIGEM_SERVICOS_PRELIMINARES = "servicos_preliminares"

TIPO_ITEM_CATALOGO_SINAPI = TIPO_ITEM_SINAPI
TIPO_ITEM_CATALOGO_PROPRIA = TIPO_ITEM_PROPRIA

NOME_SERVICOS_PRELIMINARES = "SERVIÇOS PRELIMINARES"

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
    "area_fachada_bloco": "Área de fachada (um bloco, sem esquadrias)",
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

ROTULOS_CURTOS_TIPO_CALCULO = {
    "area_fachada_bloco": "fachada/bloco",
    "area_fachada_total": "fachada total",
    "area_alvenaria_hall_total": "alvenaria hall",
    "area_laje_hall_total": "laje hall",
    "area_piso_hall_total": "piso hall",
    "perimetro_hall_rodape_total": "rodapé hall",
    "area_cobertura_total": "cobertura",
    "perimetro_paredes_externas_total": "perím. paredes",
    "perimetro_platibanda_total": "platibanda",
    "perimetro_beiral": "beiral",
    "pingadeira_total": "pingadeira",
    "esquadria_area_total": "esquadrias",
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
    "por_bloco": "blocos",
    "por_pavimento": "pavimentos",
    "por_apartamento": "apartamentos",
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


def novos_servicos_preliminares() -> dict[str, Any]:
    return {
        "nome": NOME_SERVICOS_PRELIMINARES,
        "itens": [],
    }


def catalogo_vazio() -> dict[str, Any]:
    return {
        "versao": VERSAO_CATALOGO,
        "anomalias": {},
        "servicos_preliminares": novos_servicos_preliminares(),
    }


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


def novo_fator(
    *,
    tipo_calculo: str = "fixo",
    coeficiente: float = 1.0,
) -> dict[str, Any]:
    tipo = str(tipo_calculo or "fixo")
    return {
        "tipo_calculo": tipo if tipo in TIPOS_CALCULO else "fixo",
        "coeficiente": _coeficiente_item(coeficiente),
    }


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
                    )
                )
            if fatores:
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
                )
            )
        if fatores:
            return fatores
    return [novo_fator()]


def _aplicar_fatores_no_item(item: dict[str, Any], fatores: list[dict[str, Any]]) -> dict[str, Any]:
    fatores = normalizar_fatores(fatores)
    item["fatores"] = fatores
    # Campos legados: primeiro fator (compatível com catálogos/UI antigos).
    item["tipo_calculo"] = fatores[0]["tipo_calculo"]
    item["coeficiente"] = fatores[0]["coeficiente"]
    return item


def novo_item_sinapi(
    *,
    codigo_sinapi: str = "",
    unidade: str = "m²",
    tipo_calculo: str = "area_fachada_total",
    coeficiente: float = 1.0,
    fatores: list | None = None,
    da_etapa: bool = False,
) -> dict[str, Any]:
    item = {
        "id": novo_id(),
        "tipo": TIPO_ITEM_CATALOGO_SINAPI,
        "codigo_sinapi": str(codigo_sinapi).strip(),
        "unidade": str(unidade or "m²").strip(),
        "da_etapa": bool(da_etapa),
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
) -> dict[str, Any]:
    item = {
        "id": novo_id(),
        "tipo": TIPO_ITEM_CATALOGO_PROPRIA,
        "composicao_catalogo_id": str(composicao_catalogo_id or "").strip(),
        "codigo": str(codigo or "").strip(),
        "nome": str(nome or "").strip(),
        "unidade": str(unidade or "un").strip(),
        "da_etapa": bool(da_etapa),
    }
    return _aplicar_fatores_no_item(
        item,
        fatores
        if fatores is not None
        else [novo_fator(tipo_calculo=tipo_calculo, coeficiente=coeficiente)],
    )


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
        )
    else:
        novo = novo_item_sinapi(
            codigo_sinapi=bruto.get("codigo_sinapi") or bruto.get("codigo"),
            unidade=bruto.get("unidade") or "m²",
            fatores=fatores,
            da_etapa=bool(bruto.get("da_etapa")),
        )
    if bruto.get("id"):
        novo["id"] = str(bruto.get("id"))
    return novo


def normalizar_servicos_preliminares(bruto) -> dict[str, Any]:
    base = novos_servicos_preliminares()
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
            )
            if anterior and anterior.get("id"):
                novo["id"] = str(anterior.get("id"))
                usados_ids.add(novo["id"])
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
            )
            if anterior and anterior.get("id"):
                novo["id"] = str(anterior.get("id"))
                usados_ids.add(novo["id"])
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
    base["servicos_preliminares"] = normalizar_servicos_preliminares(
        dados.get("servicos_preliminares")
    )
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
        base["anomalias"][titulo] = {"reparos": reparos}
    return base


def obter_servicos_preliminares(dados: dict | None = None) -> dict[str, Any]:
    origem = dados if dados is not None else carregar_catalogo()
    return deepcopy(
        normalizar_servicos_preliminares((origem or {}).get("servicos_preliminares"))
    )


def nomes_anomalias(dados: dict | None = None) -> list[str]:
    origem = dados if dados is not None else carregar_catalogo()
    return list((origem.get("anomalias") or {}).keys())


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
    """Copia só os códigos SINAPI da etapa; preserva cálculo/coeficiente já definidos."""
    padrao = tipo_calculo_padrao if tipo_calculo_padrao in TIPOS_CALCULO else "fixo"
    atuais = [i for i in (itens_atuais or []) if isinstance(i, dict)]
    novos: list[dict[str, Any]] = []
    usados_ids: set[str] = set()
    vistos_codigos: set[str] = set()
    for ref in (etapa or {}).get("itens") or []:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("tipo") or "") != TIPO_ITEM_SINAPI:
            continue
        codigo = str(ref.get("codigo") or "").strip()
        if not codigo or codigo in vistos_codigos:
            continue
        vistos_codigos.add(codigo)
        anterior = next(
            (
                item
                for item in atuais
                if str(item.get("codigo_sinapi") or "").strip() == codigo
            ),
            None,
        )
        if anterior:
            fatores = normalizar_fatores(anterior)
        else:
            fatores = [novo_fator(tipo_calculo=padrao, coeficiente=1)]
        novo = novo_item_sinapi(
            codigo_sinapi=codigo,
            unidade=(anterior or {}).get("unidade") or ref.get("unidade") or "un",
            fatores=fatores,
            da_etapa=True,
        )
        if anterior and anterior.get("id"):
            novo["id"] = str(anterior.get("id"))
            usados_ids.add(novo["id"])
        novos.append(novo)
    for item in atuais:
        ident = str(item.get("id") or "")
        if ident and ident in usados_ids:
            continue
        if item.get("da_etapa"):
            continue
        codigo = str(item.get("codigo_sinapi") or "").strip()
        if codigo and codigo in vistos_codigos:
            continue
        extra = _normalizar_item_catalogo(deepcopy(item)) or deepcopy(item)
        extra["da_etapa"] = False
        novos.append(extra)
    return novos


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


def valores_considerados_reparo(
    reparo: dict | None,
    quantitativos: dict | None,
    percentual,
    etapas_por_id: dict | None = None,
) -> list[tuple[float, str]]:
    """Quantidades efetivas do reparo (únicas por fórmula/unidade)."""
    reparo = reparo or {}
    quantitativos = quantitativos or {}
    fator = fator_percentual_anomalia(percentual)
    resultado: list[tuple[float, str]] = []
    vistos: set[tuple] = set()
    for item in itens_efetivos_reparo(reparo, etapas_por_id):
        fatores = normalizar_fatores(item)
        qtd = quantidade_de_item(item, quantitativos) * fator
        unid = str(item.get("unidade") or "").strip() or "un"
        marca = (
            tuple(
                (f["tipo_calculo"], round(float(f["coeficiente"]), 6)) for f in fatores
            ),
            unid,
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


def quantidade_item(tipo_calculo: str, coeficiente: float, quantitativos: dict) -> float:
    coef = float(coeficiente or 0)
    if tipo_calculo == "fixo":
        return coef
    chave = MAPA_TIPO_QUANTITATIVO.get(tipo_calculo)
    if not chave:
        return coef
    base = float(quantitativos.get(chave) or 0)
    return base * coef


def quantidade_de_item(item: dict | None, quantitativos: dict | None) -> float:
    """Produto dos fatores do item (ex.: fachada/bloco × blocos × 2)."""
    total = 1.0
    for fator in normalizar_fatores(item or {}):
        total *= quantidade_item(
            fator.get("tipo_calculo") or "fixo",
            fator.get("coeficiente") or 1,
            quantitativos or {},
        )
    return total


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
    """Resumo curto da fórmula, ex.: «fachada/bloco × blocos × 2»."""
    fatores = normalizar_fatores(item_ou_fatores)
    partes = []
    for fator in fatores:
        tipo = fator.get("tipo_calculo") or "fixo"
        coef = _coeficiente_item(fator.get("coeficiente") or 1)
        if tipo == "fixo":
            partes.append(_fmt_coef_curto(coef))
            continue
        base = ROTULOS_CURTOS_TIPO_CALCULO.get(tipo) or tipo
        if abs(coef - 1.0) < 1e-9:
            partes.append(base)
        else:
            partes.append(f"{base}×{_fmt_coef_curto(coef)}")
    return " × ".join(partes) if partes else "—"
