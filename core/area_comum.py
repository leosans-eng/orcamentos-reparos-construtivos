"""Modelo do rascunho de orçamento de Área Comum (em evolução)."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone

VERSAO_RASCUNHO = 1

TIPOS_EMPREENDIMENTO = (
    "Edifício vertical",
    "Condomínio horizontal",
    "Misto",
)

TIPOS_ESQUADRIA = (
    "Janela de correr",
    "Janela maxim-ar",
    "Janela de giro",
    "Basculante",
    "Porta de giro",
    "Porta de correr",
    "Portão",
    "Outra",
)

CAMPOS_MEDIDA = (
    ("area_fachada_m2", "Área de fachada (m²)"),
    ("area_cobertura_m2", "Área de cobertura (m²)"),
    ("area_piso_comum_m2", "Área de piso das áreas comuns (m²)"),
    ("area_parede_interna_m2", "Área de parede interna (m²)"),
    ("area_calcada_m2", "Área de calçada / passeio (m²)"),
    ("perimetro_terreno_m", "Perímetro do terreno (m)"),
    ("altura_edificacao_m", "Altura da edificação (m)"),
)

# Catálogo provisório das anomalias mais usadas — quantitativos ao vivo
# a partir das medidas globais. As composições próprias entram depois.
ANOMALIAS_MODELO = (
    {
        "id": "infiltracao_fachada",
        "nome": "Infiltração pela fachada",
        "campos": (
            {
                "id": "percentual",
                "rotulo": "% da fachada afetada",
                "unidade": "%",
            },
        ),
        "quantitativos": (
            {
                "id": "area_m2",
                "rotulo": "Área de fachada",
                "unidade": "m²",
                "medida": "area_fachada_m2",
                "campo": "percentual",
            },
        ),
    },
    {
        "id": "deterioracao_revestimento_externo",
        "nome": "Deterioração do revestimento externo",
        "campos": (
            {
                "id": "percentual",
                "rotulo": "% da fachada afetada",
                "unidade": "%",
            },
        ),
        "quantitativos": (
            {
                "id": "area_m2",
                "rotulo": "Área de fachada",
                "unidade": "m²",
                "medida": "area_fachada_m2",
                "campo": "percentual",
            },
        ),
    },
    {
        "id": "infiltracao_cobertura",
        "nome": "Infiltração pela cobertura",
        "campos": (
            {
                "id": "percentual",
                "rotulo": "% da cobertura afetada",
                "unidade": "%",
            },
        ),
        "quantitativos": (
            {
                "id": "area_m2",
                "rotulo": "Área de cobertura",
                "unidade": "m²",
                "medida": "area_cobertura_m2",
                "campo": "percentual",
            },
        ),
    },
    {
        "id": "umidade_ascendente",
        "nome": "Umidade ascendente",
        "campos": (
            {
                "id": "percentual",
                "rotulo": "% do perímetro afetado",
                "unidade": "%",
            },
        ),
        "quantitativos": (
            {
                "id": "perimetro_m",
                "rotulo": "Perímetro afetado",
                "unidade": "m",
                "medida": "perimetro_terreno_m",
                "campo": "percentual",
            },
        ),
    },
    {
        "id": "trinca_parede",
        "nome": "Trinca na parede",
        "campos": (
            {
                "id": "percentual",
                "rotulo": "% da parede interna afetada",
                "unidade": "%",
            },
        ),
        "quantitativos": (
            {
                "id": "area_m2",
                "rotulo": "Área de parede",
                "unidade": "m²",
                "medida": "area_parede_interna_m2",
                "campo": "percentual",
            },
        ),
    },
)


def novo_id() -> str:
    return str(uuid.uuid4())


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def nova_esquadria(
    *,
    tipo="",
    largura="",
    altura="",
    quantidade="1",
) -> dict:
    return {
        "id": novo_id(),
        "tipo": str(tipo or "").strip(),
        "largura_m": str(largura or "").strip(),
        "altura_m": str(altura or "").strip(),
        "quantidade": str(quantidade or "").strip(),
    }


def novo_percentual(*, nome="", valor="") -> dict:
    return {
        "id": novo_id(),
        "nome": str(nome or "").strip(),
        "valor": str(valor or "").strip(),
    }


def novo_item_anomalia_nova(
    *,
    nome_anomalia="",
    composicao_catalogo_id="",
    codigo="",
    nome_item="",
    unidade="",
    quantidade="",
) -> dict:
    return {
        "id": novo_id(),
        "nome_anomalia": str(nome_anomalia or "").strip(),
        "composicao_catalogo_id": str(composicao_catalogo_id or "").strip(),
        "codigo": str(codigo or "").strip(),
        "nome_item": str(nome_item or "").strip(),
        "unidade": str(unidade or "").strip(),
        "quantidade": str(quantidade or "").strip(),
    }


def novo_rascunho() -> dict:
    return {
        "versao": VERSAO_RASCUNHO,
        "atualizado_em": "",
        "condominio": {
            "nome": "",
            "municipio": "",
            "uf": "",
        },
        "dados_iniciais": {
            "tipo_empreendimento": "",
            "qtd_blocos": "",
            "qtd_pavimentos": "",
            "qtd_unidades": "",
            "bdi_percent": "30,45",
            "medidas": {chave: "" for chave, _rotulo in CAMPOS_MEDIDA},
            "percentuais": [],
        },
        "esquadrias": [],
        "anomalias": {item["id"]: {} for item in ANOMALIAS_MODELO},
        "anomalias_novas": [],
        "observacoes": "",
    }


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def normalizar_rascunho(dados) -> dict:
    base = novo_rascunho()
    if not isinstance(dados, dict):
        return base

    base["versao"] = VERSAO_RASCUNHO
    base["atualizado_em"] = _texto(dados.get("atualizado_em"))

    condominio = dados.get("condominio") if isinstance(dados.get("condominio"), dict) else {}
    base["condominio"]["nome"] = _texto(condominio.get("nome")).upper()
    base["condominio"]["municipio"] = _texto(condominio.get("municipio")).upper()
    base["condominio"]["uf"] = _texto(condominio.get("uf")).upper()

    iniciais = (
        dados.get("dados_iniciais")
        if isinstance(dados.get("dados_iniciais"), dict)
        else {}
    )
    tipo = _texto(iniciais.get("tipo_empreendimento"))
    base["dados_iniciais"]["tipo_empreendimento"] = (
        tipo if tipo in TIPOS_EMPREENDIMENTO else ""
    )
    base["dados_iniciais"]["qtd_blocos"] = _texto(iniciais.get("qtd_blocos"))
    base["dados_iniciais"]["qtd_pavimentos"] = _texto(iniciais.get("qtd_pavimentos"))
    base["dados_iniciais"]["qtd_unidades"] = _texto(iniciais.get("qtd_unidades"))
    bdi = _texto(iniciais.get("bdi_percent"))
    base["dados_iniciais"]["bdi_percent"] = bdi or "30,45"

    medidas_origem = iniciais.get("medidas") if isinstance(iniciais.get("medidas"), dict) else {}
    for chave, _rotulo in CAMPOS_MEDIDA:
        base["dados_iniciais"]["medidas"][chave] = _texto(medidas_origem.get(chave))

    percentuais = []
    for item in iniciais.get("percentuais") or []:
        if not isinstance(item, dict):
            continue
        percentuais.append(
            novo_percentual(nome=item.get("nome"), valor=item.get("valor"))
            if not _texto(item.get("id"))
            else {
                "id": _texto(item.get("id")) or novo_id(),
                "nome": _texto(item.get("nome")),
                "valor": _texto(item.get("valor")),
            }
        )
    base["dados_iniciais"]["percentuais"] = percentuais

    esquadrias = []
    for item in dados.get("esquadrias") or []:
        if not isinstance(item, dict):
            continue
        linha = nova_esquadria(
            tipo=item.get("tipo"),
            largura=item.get("largura_m"),
            altura=item.get("altura_m"),
            quantidade=item.get("quantidade"),
        )
        if _texto(item.get("id")):
            linha["id"] = _texto(item.get("id"))
        esquadrias.append(linha)
    base["esquadrias"] = esquadrias

    anomalias_origem = dados.get("anomalias") if isinstance(dados.get("anomalias"), dict) else {}
    for modelo in ANOMALIAS_MODELO:
        valores = anomalias_origem.get(modelo["id"])
        if not isinstance(valores, dict):
            valores = {}
        base["anomalias"][modelo["id"]] = {
            campo["id"]: _texto(valores.get(campo["id"]))
            for campo in modelo["campos"]
        }

    novas = []
    for item in dados.get("anomalias_novas") or []:
        if not isinstance(item, dict):
            continue
        linha = novo_item_anomalia_nova(
            nome_anomalia=item.get("nome_anomalia"),
            composicao_catalogo_id=item.get("composicao_catalogo_id"),
            codigo=item.get("codigo"),
            nome_item=item.get("nome_item"),
            unidade=item.get("unidade"),
            quantidade=item.get("quantidade"),
        )
        if _texto(item.get("id")):
            linha["id"] = _texto(item.get("id"))
        novas.append(linha)
    base["anomalias_novas"] = novas
    base["observacoes"] = _texto(dados.get("observacoes"))
    return base


def rascunho_para_salvar(dados: dict) -> dict:
    saida = deepcopy(normalizar_rascunho(dados))
    saida["atualizado_em"] = agora_iso()
    saida["versao"] = VERSAO_RASCUNHO
    return saida


def rascunho_tem_conteudo(dados: dict) -> bool:
    dados = normalizar_rascunho(dados)
    condominio = dados["condominio"]
    if condominio["nome"] or condominio["municipio"] or condominio["uf"]:
        return True
    iniciais = dados["dados_iniciais"]
    if (
        iniciais["tipo_empreendimento"]
        or iniciais["qtd_blocos"]
        or iniciais["qtd_pavimentos"]
        or iniciais["qtd_unidades"]
    ):
        return True
    if any(iniciais["medidas"].values()):
        return True
    if iniciais["percentuais"] or dados["esquadrias"] or dados["anomalias_novas"]:
        return True
    for valores in dados["anomalias"].values():
        if any(str(valor or "").strip() for valor in valores.values()):
            return True
    return bool(dados["observacoes"])
