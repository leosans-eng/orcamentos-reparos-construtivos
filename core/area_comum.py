"""Modelo do rascunho de orçamento de Área Comum."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone

VERSAO_RASCUNHO = 4
BDI_PADRAO = "30,62"

TIPOS_ESTRUTURA = (
    "Alvenaria Convencional",
    "Alvenaria Estrutural",
    "Blocos de Concreto",
    "Parede de Concreto",
)
TIPOS_COBERTURA = (
    "Telhas Cerâmicas",
    "Telhas de Concreto",
    "Telhas de Fibrocimento",
)

ESQUADRIAS_MODELO = (
    {"id": "j1", "rotulo": "J1 (sala)"},
    {"id": "j2", "rotulo": "J2 (dormitórios)"},
    {"id": "j3", "rotulo": "J3 (banheiro)"},
    {"id": "j4", "rotulo": "J4 (cozinha)"},
    {"id": "j5", "rotulo": "J5"},
    {"id": "j_hall_1", "rotulo": "J. Hall 1"},
    {"id": "j_hall_2", "rotulo": "J. Hall 2"},
    {"id": "porta_hall", "rotulo": "Porta do hall", "sem_perimetro": True},
)

CAMPOS_MEDIDA_EDITAVEIS = (
    ("qtd_blocos", "Quantidade de blocos"),
    ("qtd_pavimentos", "Quantidade de pavimentos"),
    ("qtd_aptos_por_pavimento", "Quantidade de apartamentos por pavimento"),
    ("area_construida_m2", "Área construída / implantação / cobertura (m²)"),
    ("qtd_aguas_telhado", "Quantidade de águas do telhado"),
    ("perimetro_beiral_m", "Perímetro de beiral — calha (m)"),
    ("perimetro_paredes_externas_bloco_m", "Perímetro de paredes externas (um bloco) (m)"),
    ("perimetro_platibanda_bloco_m", "Perímetro de platibanda (um bloco) (m)"),
    ("perimetro_hall_parede_pav_m", "Perímetro de parede do hall (um pavimento) (m)"),
    ("perimetro_hall_rodape_pav_m", "Perímetro de rodapé do hall (um pavimento) (m)"),
    ("area_laje_hall_pav_m2", "Área da laje do hall (um pavimento) (m²)"),
    ("area_piso_hall_pav_m2", "Área de piso do hall (um pavimento) (m²)"),
    ("pe_direito_m", "Pé-direito (m)"),
    ("altura_platibanda_m", "Altura da platibanda (m)"),
    ("caixas_inspecao_bloco", "Caixas de inspeção (um bloco)"),
    ("caixas_gordura_bloco", "Caixas de gordura (um bloco)"),
)

CAMPOS_MEDIDA_AUTO = (
    ("qtd_aptos_por_bloco", "Quantidade de apartamentos por bloco"),
    ("qtd_aptos_total", "Quantidade total de apartamentos"),
    ("perimetro_paredes_externas_total_m", "Perímetro de paredes externas (total) (m)"),
    ("perimetro_platibanda_total_m", "Perímetro de platibanda (total) (m)"),
    ("perimetro_hall_parede_total_m", "Perímetro de parede do hall (total) (m)"),
    ("perimetro_hall_rodape_total_m", "Perímetro de rodapé do hall (total) (m)"),
    ("area_laje_hall_total_m2", "Área da laje do hall (total) (m²)"),
    ("area_piso_hall_total_m2", "Área de piso do hall (total) (m²)"),
    ("caixas_inspecao_total", "Caixas de inspeção (total)"),
    ("caixas_gordura_total", "Caixas de gordura (total)"),
)

CAMPOS_RESUMO_FACHADA = (
    ("esquadria_area_pav_m2", "Área de esquadrias (um pavimento)", "m²"),
    ("esquadria_area_total_m2", "Área de esquadrias (total)", "m²"),
    ("esquadria_perimetro_pav_m", "Perímetro de esquadrias (um pavimento)", "m"),
    ("pingadeira_total_m", "Pingadeira (total)", "m"),
    ("area_fachada_bloco_m2", "Área de fachada (um bloco, sem esquadrias)", "m²"),
    ("area_fachada_total_m2", "Área de fachada (total, sem esquadrias)", "m²"),
    ("area_cobertura_total_m2", "Área de cobertura (total)", "m²"),
    ("area_alvenaria_hall_total_m2", "Área de alvenaria interna do hall (total)", "m²"),
)

PERCENTUAIS_MODELO = (
    (
        "troca_revestimento_fachada",
        "Troca de revestimento da fachada",
        "",
        "pct_troca_revestimento_fachada_m2",
        "m²",
    ),
    (
        "troca_revestimento_paredes_hall",
        "Troca de revestimento das paredes dos halls",
        "",
        "pct_troca_revestimento_paredes_hall_m2",
        "m²",
    ),
    (
        "troca_revestimento_tetos_hall",
        "Troca de revestimento dos tetos dos halls",
        "",
        "pct_troca_revestimento_tetos_hall_m2",
        "m²",
    ),
    (
        "troca_pisos_hall",
        "Troca de pisos do hall",
        "",
        "pct_troca_pisos_hall_m2",
        "m²",
    ),
    (
        "troca_rodape_hall",
        "Troca de rodapé do hall",
        "",
        "pct_troca_rodape_hall_m",
        "m",
    ),
    (
        "troca_estrutura_cobertura",
        "Troca de estrutura da cobertura",
        "",
        "pct_troca_estrutura_cobertura_m2",
        "m²",
    ),
    (
        "instalacao_tabeira_beiral",
        "Instalação de tabeira / beiral",
        "",
        "pct_instalacao_tabeira_beiral_m",
        "m",
    ),
    (
        "troca_telhas_cobertura",
        "Troca de telhas da cobertura",
        "",
        "pct_troca_telhas_cobertura_m2",
        "m²",
    ),
    (
        "troca_rufos_pingadeira",
        "Troca de rufos e pingadeiras",
        "",
        "pct_troca_rufos_pingadeira_m",
        "m",
    ),
    (
        "pintura_fachada",
        "Pintura da fachada",
        "100",
        "pct_pintura_fachada_m2",
        "m²",
    ),
    (
        "pintura_paredes_hall",
        "Pintura das paredes do hall",
        "",
        "pct_pintura_paredes_hall_m2",
        "m²",
    ),
    (
        "pintura_teto_hall",
        "Pintura do teto do hall",
        "",
        "pct_pintura_teto_hall_m2",
        "m²",
    ),
)

MEDIDAS_PADRAO = {
    "pe_direito_m": "2,60",
    "altura_platibanda_m": "1,00",
}


def novo_id() -> str:
    return str(uuid.uuid4())


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _desenho_normalizado(origem) -> dict:
    pontos = []
    if isinstance(origem, dict):
        for item in origem.get("pontos") or []:
            if not isinstance(item, dict):
                continue
            try:
                pontos.append({"x": float(item["x"]), "y": float(item["y"])})
            except (KeyError, TypeError, ValueError):
                continue
        fechado = bool(origem.get("fechado"))
    else:
        fechado = False
    return {"pontos": pontos, "fechado": fechado and len(pontos) >= 3}


def esquadria_vazia(modelo: dict) -> dict:
    return {
        "id": modelo["id"],
        "rotulo": modelo["rotulo"],
        "sem_perimetro": bool(modelo.get("sem_perimetro")),
        "dim_x": "",
        "dim_y": "",
        "h_peitoril": "",
        "qtd_por_pav": "",
    }


def percentuais_padrao() -> dict:
    return {item[0]: item[2] for item in PERCENTUAIS_MODELO}


def novo_item_anomalia_nova(
    *,
    nome_anomalia="",
    etapa_predefinida_id="",
    etapa_nome="",
    quantidade="",
) -> dict:
    return {
        "id": novo_id(),
        "nome_anomalia": str(nome_anomalia or "").strip(),
        "etapa_predefinida_id": str(etapa_predefinida_id or "").strip(),
        "etapa_nome": str(etapa_nome or "").strip(),
        "quantidade": str(quantidade or "").strip(),
    }


def nova_anomalia_orcamento(
    *, nome="", reparo_id="", reparo_nome="", percentual="100"
) -> dict:
    return {
        "id": novo_id(),
        "nome": str(nome or "").strip(),
        "reparo_id": str(reparo_id or "").strip(),
        "reparo_nome": str(reparo_nome or "").strip(),
        "percentual": str(percentual if percentual is not None else "100").strip() or "100",
    }


def novo_extra_orcamento(
    *,
    tipo="item",
    nome="",
    etapa_predefinida_id="",
    codigo_sinapi="",
    descricao="",
    unidade="",
    quantidade="1",
    custo_unitario=0.0,
    estado="",
) -> dict:
    return {
        "id": novo_id(),
        "tipo": "etapa" if tipo == "etapa" else "item",
        "nome": str(nome or "").strip(),
        "etapa_predefinida_id": str(etapa_predefinida_id or "").strip(),
        "codigo_sinapi": str(codigo_sinapi or "").strip(),
        "descricao": str(descricao or "").strip(),
        "unidade": str(unidade or "").strip(),
        "quantidade": str(quantidade or "1").strip() or "1",
        "custo_unitario": custo_unitario,
        "estado": str(estado or "").strip(),
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
            "bdi_percent": BDI_PADRAO,
            "medidas": {
                **{chave: "" for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS},
                **MEDIDAS_PADRAO,
            },
            "percentuais": percentuais_padrao(),
            "desenho_principal": {"pontos": [], "fechado": False},
            "tipo_estrutura": "",
            "tipo_cobertura": "",
        },
        "esquadrias": [esquadria_vazia(item) for item in ESQUADRIAS_MODELO],
        "anomalias_orcamento": [],
        "extras_orcamento": [],
        "orcamento": {"grupos": []},
        "observacoes": "",
    }


def _esquadrias_normalizadas(origem) -> list[dict]:
    por_id = {}
    if isinstance(origem, list):
        for item in origem:
            if isinstance(item, dict) and _texto(item.get("id")):
                por_id[_texto(item.get("id"))] = item
    saida = []
    for modelo in ESQUADRIAS_MODELO:
        base = esquadria_vazia(modelo)
        extra = por_id.get(modelo["id"], {})
        base["dim_x"] = _texto(extra.get("dim_x") or extra.get("largura_m"))
        base["dim_y"] = _texto(extra.get("dim_y") or extra.get("altura_m"))
        base["h_peitoril"] = _texto(extra.get("h_peitoril"))
        base["qtd_por_pav"] = _texto(
            extra.get("qtd_por_pav") or extra.get("quantidade")
        )
        saida.append(base)
    return saida


def _percentuais_normalizados(origem) -> dict:
    padrao = percentuais_padrao()
    if isinstance(origem, dict):
        for chave in padrao:
            if chave in origem:
                padrao[chave] = _texto(origem.get(chave))
        return padrao
    if isinstance(origem, list):
        nomes = {item[1]: item[0] for item in PERCENTUAIS_MODELO}
        for item in origem:
            if not isinstance(item, dict):
                continue
            chave = _texto(item.get("id"))
            nome = _texto(item.get("nome"))
            if chave in padrao:
                padrao[chave] = _texto(item.get("valor"))
            elif nome in nomes:
                padrao[nomes[nome]] = _texto(item.get("valor"))
    return padrao


def _opcao_conhecida(valor, opcoes) -> str:
    texto = _texto(valor)
    return texto if texto in opcoes else ""


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
    bdi = _texto(iniciais.get("bdi_percent"))
    base["dados_iniciais"]["bdi_percent"] = bdi or BDI_PADRAO

    medidas_origem = iniciais.get("medidas") if isinstance(iniciais.get("medidas"), dict) else {}
    # Compatibilidade com rascunhos da prévia (v1).
    alias = {
        "qtd_blocos": ("qtd_blocos",),
        "qtd_pavimentos": ("qtd_pavimentos",),
        "qtd_aptos_por_pavimento": ("qtd_unidades", "qtd_aptos_por_pavimento"),
        "area_construida_m2": ("area_fachada_m2", "area_construida_m2"),
        "pe_direito_m": ("altura_edificacao_m", "pe_direito_m"),
    }
    for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS:
        valor = ""
        for cand in alias.get(chave, (chave,)):
            texto = _texto(medidas_origem.get(cand) or iniciais.get(cand))
            if texto:
                valor = texto
                break
        if not valor:
            valor = _texto(medidas_origem.get(chave))
        if not valor and chave in MEDIDAS_PADRAO:
            valor = MEDIDAS_PADRAO[chave]
        base["dados_iniciais"]["medidas"][chave] = valor

    base["dados_iniciais"]["percentuais"] = _percentuais_normalizados(
        iniciais.get("percentuais")
    )
    base["dados_iniciais"]["desenho_principal"] = _desenho_normalizado(
        iniciais.get("desenho_principal") or dados.get("desenho_principal")
    )
    base["dados_iniciais"]["tipo_estrutura"] = _opcao_conhecida(
        iniciais.get("tipo_estrutura"), TIPOS_ESTRUTURA
    )
    base["dados_iniciais"]["tipo_cobertura"] = _opcao_conhecida(
        iniciais.get("tipo_cobertura"), TIPOS_COBERTURA
    )
    base["esquadrias"] = _esquadrias_normalizadas(dados.get("esquadrias"))

    orcamento = []
    for item in dados.get("anomalias_orcamento") or []:
        if not isinstance(item, dict):
            continue
        linha = nova_anomalia_orcamento(
            nome=item.get("nome"),
            reparo_id=item.get("reparo_id"),
            reparo_nome=item.get("reparo_nome"),
            percentual=item.get("percentual") or "100",
        )
        if _texto(item.get("id")):
            linha["id"] = _texto(item.get("id"))
        orcamento.append(linha)
    base["anomalias_orcamento"] = orcamento

    extras = []
    origem_extras = dados.get("extras_orcamento")
    if not isinstance(origem_extras, list):
        origem_extras = []
        for item in dados.get("anomalias_novas") or []:
            if not isinstance(item, dict):
                continue
            origem_extras.append(
                {
                    "tipo": "etapa",
                    "nome": item.get("etapa_nome") or item.get("nome_anomalia"),
                    "etapa_predefinida_id": item.get("etapa_predefinida_id"),
                    "quantidade": item.get("quantidade") or "1",
                    "id": item.get("id"),
                }
            )
    for item in origem_extras:
        if not isinstance(item, dict):
            continue
        linha = novo_extra_orcamento(
            tipo=item.get("tipo") or "item",
            nome=item.get("nome") or item.get("descricao"),
            etapa_predefinida_id=item.get("etapa_predefinida_id"),
            codigo_sinapi=item.get("codigo_sinapi"),
            descricao=item.get("descricao"),
            unidade=item.get("unidade"),
            quantidade=item.get("quantidade") or "1",
            custo_unitario=item.get("custo_unitario") or 0,
            estado=item.get("estado"),
        )
        if _texto(item.get("id")):
            linha["id"] = _texto(item.get("id"))
        extras.append(linha)
    base["extras_orcamento"] = extras
    orcamento_dados = dados.get("orcamento")
    if isinstance(orcamento_dados, dict):
        grupos = orcamento_dados.get("grupos")
        base["orcamento"] = {
            "id": _texto(orcamento_dados.get("id")),
            "nome": _texto(orcamento_dados.get("nome")),
            "bdi_percent": orcamento_dados.get("bdi_percent"),
            "estado_referencia": _texto(orcamento_dados.get("estado_referencia")),
            "grupos": deepcopy(grupos) if isinstance(grupos, list) else [],
        }
    else:
        base["orcamento"] = {"grupos": []}
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
    medidas = iniciais["medidas"]
    for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS:
        if chave in MEDIDAS_PADRAO and medidas.get(chave) == MEDIDAS_PADRAO[chave]:
            continue
        if medidas.get(chave):
            return True
    if iniciais.get("tipo_estrutura") or iniciais.get("tipo_cobertura"):
        return True
    if iniciais["percentuais"] != percentuais_padrao():
        return True
    if any(
        item.get("dim_x") or item.get("dim_y") or item.get("qtd_por_pav") or item.get("h_peitoril")
        for item in dados["esquadrias"]
    ):
        return True
    if dados["anomalias_orcamento"] or dados.get("extras_orcamento"):
        return True
    grupos = (dados.get("orcamento") or {}).get("grupos") or []
    if grupos:
        return True
    if (iniciais.get("desenho_principal") or {}).get("pontos"):
        return True
    return bool(dados["observacoes"])
