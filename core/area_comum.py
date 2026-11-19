"""Modelo do rascunho de orçamento de Área Comum."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone

VERSAO_RASCUNHO = 6
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
    {"id": "cobogo_1", "rotulo": "Cobogó 1", "cobogo": True},
    {"id": "cobogo_2", "rotulo": "Cobogó 2", "cobogo": True},
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
    ("qtd_aptos_por_bloco", "Apartamentos por bloco", ""),
    ("qtd_aptos_total", "Apartamentos no total", ""),
    ("perimetro_paredes_externas_total_m", "Perímetro de Paredes externas (total)", "m"),
    ("perimetro_platibanda_total_m", "Perímetro de Platibanda (total)", "m"),
    ("perimetro_hall_parede_total_m", "Perímetro de Paredes do hall (total)", "m"),
    ("perimetro_hall_rodape_total_m", "Perímetro de Rodapé do hall (total)", "m"),
    ("area_laje_hall_total_m2", "Área da Laje do hall (total)", "m²"),
    ("area_piso_hall_total_m2", "Área do Piso do hall (total)", "m²"),
    ("area_cobertura_total_m2", "Área da Cobertura (total)", "m²"),
    ("area_alvenaria_hall_total_m2", "Área de Paredes internas do hall (total)", "m²"),
    ("caixas_inspecao_total", "Caixas de inspeção", ""),
    ("caixas_gordura_total", "Caixas de gordura", ""),
)

CAMPOS_RESUMO_FACHADA = (
    ("esquadria_area_pav_m2", "Área de esquadrias (por pavimento)", "m²"),
    ("esquadria_area_total_m2", "Área de esquadrias (total)", "m²"),
    ("janela_area_pav_m2", "Área de janelas (por pavimento)", "m²"),
    ("janela_area_total_m2", "Área de janelas (total)", "m²"),
    ("esquadria_perimetro_pav_m", "Perímetro de esquadrias (por pavimento)", "m"),
    ("esquadria_perimetro_total_m", "Perímetro de esquadrias (total)", "m"),
    ("cobogo_area_pav_m2", "Área de cobogós (por pavimento)", "m²"),
    ("cobogo_area_total_m2", "Área de cobogós (total)", "m²"),
    ("cobogo_perimetro_pav_m", "Perímetro de cobogós (por pavimento)", "m"),
    ("cobogo_perimetro_total_m", "Perímetro de cobogós (total)", "m"),
    ("pingadeira_total_m", "Pingadeira (total)", "m"),
    ("esquadria_qtd_janelas_total", "Quantidade de esquadrias (janelas, total)", ""),
    ("area_fachada_bloco_m2", "Área de fachada (por bloco, sem esquadrias)", "m²"),
    ("area_fachada_total_m2", "Área de fachada (total, sem esquadrias)", "m²"),
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
    (
        "troca_tampas_inspecao",
        "Troca de tampas das caixas de inspeção",
        "",
        "pct_troca_tampas_inspecao_un",
        "un",
    ),
    (
        "troca_tampas_gordura",
        "Troca de tampas das caixas de gordura",
        "",
        "pct_troca_tampas_gordura_un",
        "un",
    ),
    (
        "troca_calcadas",
        "Troca de calçadas e caminhos",
        "",
        "pct_troca_calcadas_m2",
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


def _camada_desenho_normalizada(origem) -> dict:
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


def _desenho_normalizado(origem) -> dict:
    """Aceita formato legado (um polígono) e o novo (externa + hall)."""
    vazio = {
        "externa": {"pontos": [], "fechado": False},
        "hall": {"pontos": [], "fechado": False},
    }
    if not isinstance(origem, dict):
        return vazio
    if isinstance(origem.get("externa"), dict) or isinstance(origem.get("hall"), dict):
        return {
            "externa": _camada_desenho_normalizada(origem.get("externa") or {}),
            "hall": _camada_desenho_normalizada(origem.get("hall") or {}),
        }
    # Legado: um único polígono vira a camada externa.
    return {
        "externa": _camada_desenho_normalizada(origem),
        "hall": {"pontos": [], "fechado": False},
    }


def esquadria_vazia(modelo: dict) -> dict:
    return {
        "id": modelo["id"],
        "rotulo": modelo["rotulo"],
        "sem_perimetro": bool(modelo.get("sem_perimetro")),
        "cobogo": bool(modelo.get("cobogo")),
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
    *, nome="", reparo_id="", reparo_nome="", percentual="100", variaveis=None,
    local="residencial",
) -> dict:
    linha = {
        "id": novo_id(),
        "nome": str(nome or "").strip(),
        "reparo_id": str(reparo_id or "").strip(),
        "reparo_nome": str(reparo_nome or "").strip(),
        "percentual": str(percentual if percentual is not None else "100").strip() or "100",
        "local": str(local or "").strip() or "residencial",
    }
    guardadas = _variaveis_normalizadas(variaveis)
    if guardadas:
        linha["variaveis"] = guardadas
    return linha


def _variaveis_normalizadas(origem) -> list[dict]:
    saida = []
    if not isinstance(origem, list):
        return saida
    for item in origem:
        if not isinstance(item, dict):
            continue
        pergunta = str(item.get("pergunta") or "").strip()
        if not pergunta:
            continue
        saida.append(
            {
                "pergunta": pergunta,
                "valor": str(
                    item.get("valor") if item.get("valor") is not None else ""
                ).strip(),
            }
        )
    return saida


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


# ---------------------------------------------------------------- estruturas
# Um condomínio tem uma ou mais estruturas: N unidades iguais com a mesma
# planta (ex.: "Bloco padrão × 15", "Bloco adaptado × 3", "Salão de festas × 1").
# Blocos residenciais somam entre si; outras edificações (salão, guarita,
# portaria...) ficam de fora do "por bloco" e não têm hall nem apartamentos.

TIPO_RESIDENCIAL = "residencial"
TIPO_OUTRA = "outra"

CHAVES_MEDIDA_CONDOMINIO = ("caixas_inspecao_bloco", "caixas_gordura_bloco")
CHAVES_PCT_CONDOMINIO = ("troca_tampas_inspecao", "troca_tampas_gordura", "troca_calcadas")
CHAVES_MEDIDA_ESTRUTURA = tuple(
    chave
    for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS
    if chave != "qtd_blocos" and chave not in CHAVES_MEDIDA_CONDOMINIO
)
CHAVES_PCT_ESTRUTURA = tuple(
    item[0] for item in PERCENTUAIS_MODELO if item[0] not in CHAVES_PCT_CONDOMINIO
)
# Só existem em bloco residencial.
CHAVES_MEDIDA_SO_RESIDENCIAL = (
    "qtd_aptos_por_pavimento",
    "perimetro_hall_parede_pav_m",
    "perimetro_hall_rodape_pav_m",
    "area_laje_hall_pav_m2",
    "area_piso_hall_pav_m2",
)
CHAVES_PCT_SO_RESIDENCIAL = (
    "troca_revestimento_paredes_hall",
    "troca_revestimento_tetos_hall",
    "troca_pisos_hall",
    "troca_rodape_hall",
    "pintura_paredes_hall",
    "pintura_teto_hall",
)
# Esquadrias de outra edificação (fixas por enquanto), com o rótulo a mostrar.
ESQUADRIAS_OUTRA_EDIFICACAO = {
    "j1": "J1",
    "j2": "J2",
    "cobogo_1": "Cobogó 1",
    "cobogo_2": "Cobogó 2",
    "porta_hall": "Porta",
}
# Quantitativos que vêm do condomínio, não das estruturas.
CHAVES_QTD_CONDOMINIO = (
    "caixas_inspecao_bloco",
    "caixas_inspecao_total",
    "caixas_gordura_bloco",
    "caixas_gordura_total",
    "pct_troca_tampas_inspecao_un",
    "pct_troca_tampas_gordura_un",
    "pct_troca_calcadas_m2",
)


def _desenho_vazio() -> dict:
    return {
        "externa": {"pontos": [], "fechado": False},
        "hall": {"pontos": [], "fechado": False},
    }


def residencial(estrutura: dict) -> bool:
    return (estrutura or {}).get("tipo") != TIPO_OUTRA


def esquadrias_da_estrutura(tipo: str) -> list[tuple[dict, str]]:
    """Modelos de esquadria usados no tipo de estrutura, com o rótulo a mostrar."""
    if tipo == TIPO_OUTRA:
        return [
            (modelo, ESQUADRIAS_OUTRA_EDIFICACAO[modelo["id"]])
            for modelo in ESQUADRIAS_MODELO
            if modelo["id"] in ESQUADRIAS_OUTRA_EDIFICACAO
        ]
    return [(modelo, modelo["rotulo"]) for modelo in ESQUADRIAS_MODELO]


def nova_estrutura(nome="Bloco padrão", tipo=TIPO_RESIDENCIAL, quantidade="") -> dict:
    padrao_pct = percentuais_padrao()
    return {
        "id": novo_id(),
        "nome": _texto(nome) or "Bloco padrão",
        "tipo": TIPO_OUTRA if tipo == TIPO_OUTRA else TIPO_RESIDENCIAL,
        "quantidade": _texto(quantidade),
        "tipo_estrutura": "",
        "tipo_cobertura": "",
        "medidas": {chave: MEDIDAS_PADRAO.get(chave, "") for chave in CHAVES_MEDIDA_ESTRUTURA},
        "percentuais": {chave: padrao_pct[chave] for chave in CHAVES_PCT_ESTRUTURA},
        "esquadrias": [esquadria_vazia(item) for item in ESQUADRIAS_MODELO],
        "desenho": _desenho_vazio(),
    }


def normalizar_estrutura(origem) -> dict:
    base = nova_estrutura()
    if not isinstance(origem, dict):
        return base
    if _texto(origem.get("id")):
        base["id"] = _texto(origem.get("id"))
    base["nome"] = _texto(origem.get("nome")) or base["nome"]
    base["tipo"] = TIPO_OUTRA if origem.get("tipo") == TIPO_OUTRA else TIPO_RESIDENCIAL
    base["quantidade"] = _texto(origem.get("quantidade"))
    base["tipo_estrutura"] = _opcao_conhecida(origem.get("tipo_estrutura"), TIPOS_ESTRUTURA)
    base["tipo_cobertura"] = _opcao_conhecida(origem.get("tipo_cobertura"), TIPOS_COBERTURA)
    medidas = origem.get("medidas") if isinstance(origem.get("medidas"), dict) else {}
    for chave in CHAVES_MEDIDA_ESTRUTURA:
        if chave in medidas:
            base["medidas"][chave] = _texto(medidas.get(chave))
    percentuais = _percentuais_normalizados(origem.get("percentuais"))
    base["percentuais"] = {chave: percentuais[chave] for chave in CHAVES_PCT_ESTRUTURA}
    base["esquadrias"] = _esquadrias_normalizadas(origem.get("esquadrias"))
    base["desenho"] = _desenho_normalizado(origem.get("desenho"))
    return base


def quantitativos_da_estrutura(estrutura: dict, *, blocos=None) -> dict:
    """Quantitativos de uma estrutura (todas as suas unidades iguais)."""
    from core.area_comum_calculos import calcular_quantitativos

    estrutura = estrutura or {}
    medidas = dict(estrutura.get("medidas") or {})
    medidas["qtd_blocos"] = estrutura.get("quantidade") if blocos is None else blocos
    percentuais = dict(estrutura.get("percentuais") or {})
    if not residencial(estrutura):
        for chave in CHAVES_MEDIDA_SO_RESIDENCIAL:
            medidas[chave] = ""
        for chave in CHAVES_PCT_SO_RESIDENCIAL:
            percentuais[chave] = ""
    usadas = {modelo["id"] for modelo, _r in esquadrias_da_estrutura(estrutura.get("tipo"))}
    esquadrias = [e for e in estrutura.get("esquadrias") or [] if e.get("id") in usadas]
    return calcular_quantitativos(medidas, esquadrias, percentuais)


def blocos_residenciais(dados: dict) -> float:
    """Soma das unidades de todas as estruturas residenciais ("por bloco")."""
    from core.area_comum_calculos import numero

    return sum(
        numero(e.get("quantidade"))
        for e in (dados or {}).get("estruturas") or []
        if residencial(e)
    )


def quantitativos_do_condominio(dados: dict) -> dict:
    """Caixas e calçadas: valem para o condomínio, com "por bloco" = blocos residenciais."""
    from core.area_comum_calculos import calcular_quantitativos

    iniciais = (dados or {}).get("dados_iniciais") or {}
    medidas = dict(iniciais.get("medidas") or {})
    medidas["qtd_blocos"] = blocos_residenciais(dados)
    return calcular_quantitativos(medidas, [], dict(iniciais.get("percentuais") or {}))


def quantitativos_do_rascunho(dados: dict):
    """O que as abas 2 e 3 usam: blocos residenciais somados + itens do condomínio."""
    from core.area_comum_calculos import QuantitativosEstruturas

    partes = [
        quantitativos_da_estrutura(e)
        for e in (dados or {}).get("estruturas") or []
        if residencial(e)
    ]
    condominio = quantitativos_do_condominio(dados)
    extras = {chave: condominio.get(chave, 0.0) for chave in CHAVES_QTD_CONDOMINIO}
    return QuantitativosEstruturas(partes, extras)


# ---------------------------------------------------------------- locais
# Cada anomalia da aba 2 acontece num local, e usa os quantitativos dele.
LOCAL_RESIDENCIAL = "residencial"
LOCAL_CONDOMINIO = "condominio"
ROTULO_LOCAL_RESIDENCIAL = "Blocos residenciais"
ROTULO_LOCAL_CONDOMINIO = "Todo o condomínio"


def locais_do_rascunho(dados: dict) -> list[tuple[str, str]]:
    """(chave, rótulo) dos locais: blocos residenciais, cada outra edificação e o condomínio."""
    locais = [(LOCAL_RESIDENCIAL, ROTULO_LOCAL_RESIDENCIAL)]
    for estrutura in (dados or {}).get("estruturas") or []:
        if not residencial(estrutura):
            locais.append((estrutura.get("id"), estrutura.get("nome") or "Outra edificação"))
    locais.append((LOCAL_CONDOMINIO, ROTULO_LOCAL_CONDOMINIO))
    return locais


def local_valido(dados: dict, local) -> str:
    """O local, ou "Blocos residenciais" se ele não existe mais."""
    chaves = {chave for chave, _rotulo in locais_do_rascunho(dados)}
    return local if local in chaves else LOCAL_RESIDENCIAL


def estruturas_do_local(dados: dict, local) -> list[dict]:
    estruturas = (dados or {}).get("estruturas") or []
    if local == LOCAL_CONDOMINIO:
        return list(estruturas)
    if local == LOCAL_RESIDENCIAL:
        return [e for e in estruturas if residencial(e)]
    return [e for e in estruturas if e.get("id") == local]


def quantitativos_por_local(dados: dict) -> dict:
    """Quantitativos de cada local (chave do local -> QuantitativosEstruturas).

    Blocos residenciais e "Todo o condomínio" incluem caixas e calçadas; uma
    outra edificação usa só as medidas dela.
    """
    from core.area_comum_calculos import QuantitativosEstruturas

    condominio = quantitativos_do_condominio(dados)
    extras = {chave: condominio.get(chave, 0.0) for chave in CHAVES_QTD_CONDOMINIO}
    por_id = {
        e.get("id"): quantitativos_da_estrutura(e)
        for e in (dados or {}).get("estruturas") or []
    }
    saida = {}
    for chave, _rotulo in locais_do_rascunho(dados):
        partes = [por_id[e.get("id")] for e in estruturas_do_local(dados, chave)]
        tem_condominio = chave in (LOCAL_RESIDENCIAL, LOCAL_CONDOMINIO)
        saida[chave] = QuantitativosEstruturas(partes, extras if tem_condominio else None)
    return saida


def novo_rascunho() -> dict:
    padrao_pct = percentuais_padrao()
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
            "medidas": {chave: "" for chave in CHAVES_MEDIDA_CONDOMINIO},
            "percentuais": {chave: padrao_pct[chave] for chave in CHAVES_PCT_CONDOMINIO},
        },
        "estruturas": [nova_estrutura()],
        "anomalias_orcamento": [],
        "considerar_servicos_preliminares": True,
        "considerar_pintura": True,
        "pintura_fachada_manual": False,
        "duas_demaos_fundo_selador": True,
        "considerar_destinacao_entulho": True,
        "considerar_limpeza_geral": True,
        "extras_orcamento": [],
        "orcamento": {"grupos": []},
        "orcamento_customizado_id": "",
        "observacoes": "",
    }


def _esquadrias_normalizadas(origem) -> list[dict]:
    por_id = {}
    if isinstance(origem, list):
        for item in origem:
            if isinstance(item, dict) and _texto(item.get("id")):
                por_id[_texto(item.get("id"))] = item
    if "cobogo" in por_id and "cobogo_1" not in por_id:
        por_id["cobogo_1"] = por_id["cobogo"]
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


def _estrutura_do_formato_antigo(dados: dict, iniciais: dict):
    """Rascunho de um bloco só -> (medidas do condomínio, percentuais, estrutura)."""
    medidas_origem = iniciais.get("medidas") if isinstance(iniciais.get("medidas"), dict) else {}
    # Nomes antigos de alguns campos (rascunhos da prévia).
    alias = {
        "qtd_aptos_por_pavimento": ("qtd_unidades", "qtd_aptos_por_pavimento"),
        "area_construida_m2": ("area_fachada_m2", "area_construida_m2"),
        "pe_direito_m": ("altura_edificacao_m", "pe_direito_m"),
    }
    medidas = {}
    for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS:
        valor = ""
        for cand in alias.get(chave, (chave,)):
            valor = _texto(medidas_origem.get(cand) or iniciais.get(cand))
            if valor:
                break
        if not valor and chave in MEDIDAS_PADRAO:
            valor = MEDIDAS_PADRAO[chave]
        medidas[chave] = valor
    percentuais = _percentuais_normalizados(iniciais.get("percentuais"))
    estrutura = normalizar_estrutura(
        {
            "nome": "Bloco padrão",
            "tipo": TIPO_RESIDENCIAL,
            "quantidade": medidas.get("qtd_blocos", ""),
            "tipo_estrutura": iniciais.get("tipo_estrutura"),
            "tipo_cobertura": iniciais.get("tipo_cobertura"),
            "medidas": medidas,
            "percentuais": percentuais,
            "esquadrias": dados.get("esquadrias"),
            "desenho": iniciais.get("desenho_principal") or dados.get("desenho_principal"),
        }
    )
    return medidas, percentuais, estrutura


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

    estruturas = dados.get("estruturas")
    if isinstance(estruturas, list) and any(isinstance(e, dict) for e in estruturas):
        base["estruturas"] = [normalizar_estrutura(e) for e in estruturas if isinstance(e, dict)]
        medidas_cond = iniciais.get("medidas") if isinstance(iniciais.get("medidas"), dict) else {}
        pct_cond = _percentuais_normalizados(iniciais.get("percentuais"))
    else:
        # Formato anterior (um bloco só): vira a estrutura "Bloco padrão".
        medidas_cond, pct_cond, unica = _estrutura_do_formato_antigo(dados, iniciais)
        base["estruturas"] = [unica]
    for chave in CHAVES_MEDIDA_CONDOMINIO:
        base["dados_iniciais"]["medidas"][chave] = _texto(medidas_cond.get(chave))
    for chave in CHAVES_PCT_CONDOMINIO:
        base["dados_iniciais"]["percentuais"][chave] = pct_cond.get(chave, "")

    orcamento = []
    for item in dados.get("anomalias_orcamento") or []:
        if not isinstance(item, dict):
            continue
        linha = nova_anomalia_orcamento(
            nome=item.get("nome"),
            reparo_id=item.get("reparo_id"),
            reparo_nome=item.get("reparo_nome"),
            percentual=item.get("percentual") or "100",
            variaveis=item.get("variaveis"),
            local=item.get("local"),
        )
        if _texto(item.get("id")):
            linha["id"] = _texto(item.get("id"))
        orcamento.append(linha)
    base["anomalias_orcamento"] = orcamento
    if "considerar_servicos_preliminares" in dados:
        base["considerar_servicos_preliminares"] = bool(
            dados.get("considerar_servicos_preliminares")
        )
    else:
        base["considerar_servicos_preliminares"] = True
    if "considerar_pintura" in dados:
        base["considerar_pintura"] = bool(dados.get("considerar_pintura"))
    else:
        base["considerar_pintura"] = True
    # None = rascunho antigo sem a informação; a interface decide comparando
    # o percentual salvo com o das anomalias.
    manual = dados.get("pintura_fachada_manual")
    base["pintura_fachada_manual"] = None if manual is None else bool(manual)
    if "duas_demaos_fundo_selador" in dados:
        base["duas_demaos_fundo_selador"] = bool(dados.get("duas_demaos_fundo_selador"))
    if "considerar_destinacao_entulho" in dados:
        base["considerar_destinacao_entulho"] = bool(
            dados.get("considerar_destinacao_entulho")
        )
    else:
        base["considerar_destinacao_entulho"] = True
    if "considerar_limpeza_geral" in dados:
        base["considerar_limpeza_geral"] = bool(dados.get("considerar_limpeza_geral"))
    else:
        base["considerar_limpeza_geral"] = True

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
    base["orcamento_customizado_id"] = _texto(dados.get("orcamento_customizado_id"))
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
    if any(iniciais["medidas"].values()):
        return True
    padrao_pct = percentuais_padrao()
    if any(iniciais["percentuais"].get(c, "") != padrao_pct[c] for c in CHAVES_PCT_CONDOMINIO):
        return True
    estruturas = dados["estruturas"]
    if len(estruturas) > 1:
        return True
    for estrutura in estruturas:
        if _estrutura_tem_conteudo(estrutura):
            return True
    if dados["anomalias_orcamento"] or dados.get("extras_orcamento"):
        return True
    grupos = (dados.get("orcamento") or {}).get("grupos") or []
    if grupos:
        return True
    return bool(dados["observacoes"])


def _estrutura_tem_conteudo(estrutura: dict) -> bool:
    vazia = nova_estrutura()
    if estrutura.get("quantidade") or estrutura.get("tipo") != vazia["tipo"]:
        return True
    if estrutura.get("nome") != vazia["nome"]:
        return True
    if estrutura.get("tipo_estrutura") or estrutura.get("tipo_cobertura"):
        return True
    if estrutura.get("medidas") != vazia["medidas"]:
        return True
    if estrutura.get("percentuais") != vazia["percentuais"]:
        return True
    if any(
        item.get("dim_x") or item.get("dim_y") or item.get("qtd_por_pav") or item.get("h_peitoril")
        for item in estrutura.get("esquadrias") or []
    ):
        return True
    desenho = estrutura.get("desenho") or {}
    return bool(
        (desenho.get("externa") or {}).get("pontos") or (desenho.get("hall") or {}).get("pontos")
    )
