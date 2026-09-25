"""Cálculos da Área Comum"""

from __future__ import annotations

import ast
import operator as op
import re

# Folga da pingadeira (m) e acréscimo de pé-direito na fachada (m), da planilha.
FOLGA_PINGADEIRA_M = 0.08
ACRESCIMO_LAJE_FACHADA_M = 0.1

_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def parse_decimal_br(texto) -> float:
    normalizado = str(texto).strip()
    if not normalizado:
        raise ValueError("valor vazio")
    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    return float(normalizado)


def parse_expressao(texto) -> float:
    """Aceita 12,5, 5*6, 1/4, (1,5+2)*3."""
    bruto = str(texto).strip().replace(" ", "")
    if not bruto:
        raise ValueError("valor vazio")
    if not re.search(r"[+\-*/()]", bruto):
        return parse_decimal_br(bruto)
    expressao = bruto.replace(",", ".")
    if not re.fullmatch(r"[0-9+\-*/().]+", expressao):
        raise ValueError("expressão inválida")

    def _avaliar(no):
        if isinstance(no, ast.Expression):
            return _avaliar(no.body)
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
            return float(no.value)
        if isinstance(no, ast.UnaryOp) and type(no.op) in _OPS:
            return _OPS[type(no.op)](_avaliar(no.operand))
        if isinstance(no, ast.BinOp) and type(no.op) in _OPS:
            direito = _avaliar(no.right)
            if isinstance(no.op, ast.Div) and direito == 0:
                raise ValueError("divisão por zero")
            return _OPS[type(no.op)](_avaliar(no.left), direito)
        raise ValueError("expressão inválida")

    try:
        return float(_avaliar(ast.parse(expressao, mode="eval")))
    except (SyntaxError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError("expressão inválida") from exc


def numero(texto, padrao: float = 0.0, *, percentual: bool = False) -> float:
    bruto = "" if texto is None else str(texto).strip()
    if not bruto:
        return padrao
    try:
        valor = parse_expressao(bruto)
    except (TypeError, ValueError):
        return padrao
    if percentual:
        compacto = bruto.replace(" ", "")
        if "/" in compacto and 0 < abs(valor) <= 1:
            valor *= 100.0
    return valor


def _primeiro_preenchido(*valores, padrao: float = 0.0) -> float:
    for valor in valores:
        if valor is None:
            continue
        if isinstance(valor, str) and not str(valor).strip():
            continue
        n = numero(valor, padrao=float("nan"))
        if n == n:  # não é NaN
            return n
    return padrao


def calcular_linha_esquadria(linha: dict) -> dict[str, float]:
    dim_x = numero(linha.get("dim_x"))
    dim_y = numero(linha.get("dim_y"))
    qtd = numero(linha.get("qtd_por_pav"))
    area = dim_x * dim_y * qtd
    pingadeira = (FOLGA_PINGADEIRA_M + dim_x) * qtd if (dim_x or qtd) else 0.0
    if linha.get("sem_perimetro"):
        perimetro = 0.0
    else:
        perimetro = 2.0 * (dim_x + dim_y) * qtd
    return {
        "perimetro_pav_m": perimetro,
        "pingadeira_pav_m": pingadeira,
        "area_pav_m2": area,
    }


def calcular_quantitativos(medidas: dict, esquadrias: list[dict], percentuais: dict) -> dict[str, float]:
    """Devolve todos os quantitativos usados na tela e, depois, no orçamento."""
    m = medidas or {}
    blocos = numero(m.get("qtd_blocos"))
    pavimentos = numero(m.get("qtd_pavimentos"))
    aptos_pav = numero(m.get("qtd_aptos_por_pavimento"))
    area_const = numero(m.get("area_construida_m2"))
    aguas = numero(m.get("qtd_aguas_telhado"))
    beiral = numero(m.get("perimetro_beiral_m"))
    peri_ext_bloco = numero(m.get("perimetro_paredes_externas_bloco_m"))
    peri_plat_bloco = numero(m.get("perimetro_platibanda_bloco_m"))
    peri_hall_parede_pav = numero(m.get("perimetro_hall_parede_pav_m"))
    peri_hall_rodape_pav = _primeiro_preenchido(
        m.get("perimetro_hall_rodape_pav_m"),
        m.get("perimetro_hall_parede_pav_m"),
    )
    area_laje_pav = numero(m.get("area_laje_hall_pav_m2"))
    area_piso_pav = _primeiro_preenchido(
        m.get("area_piso_hall_pav_m2"),
        m.get("area_laje_hall_pav_m2"),
    )
    pe_direito = numero(m.get("pe_direito_m"))
    alt_plat = numero(m.get("altura_platibanda_m"))
    cx_insp_bloco = numero(m.get("caixas_inspecao_bloco"))
    cx_gord_bloco = numero(m.get("caixas_gordura_bloco"))

    aptos_bloco = aptos_pav * pavimentos
    aptos_total = aptos_bloco * blocos
    peri_ext_total = peri_ext_bloco * blocos
    peri_plat_total = peri_plat_bloco * blocos
    peri_hall_parede_total = peri_hall_parede_pav * pavimentos * blocos
    peri_hall_rodape_total = peri_hall_rodape_pav * pavimentos * blocos
    area_laje_total = area_laje_pav * pavimentos * blocos
    area_piso_total = area_piso_pav * pavimentos * blocos
    cx_insp_total = cx_insp_bloco * blocos
    cx_gord_total = cx_gord_bloco * blocos

    esq_qtd_pav = 0.0
    esq_perimetro_pav = 0.0
    esq_pingadeira_pav = 0.0
    esq_area_pav = 0.0
    linhas_esq = {}
    for linha in esquadrias or []:
        ident = str(linha.get("id") or "")
        calc = calcular_linha_esquadria(linha)
        qtd_linha = numero(linha.get("qtd_por_pav"))
        calc["qtd_por_pav"] = qtd_linha
        linhas_esq[ident] = calc
        esq_qtd_pav += qtd_linha
        esq_perimetro_pav += calc["perimetro_pav_m"]
        esq_pingadeira_pav += calc["pingadeira_pav_m"]
        esq_area_pav += calc["area_pav_m2"]

    esq_area_total = esq_area_pav * pavimentos * blocos
    pingadeira_bloco = esq_pingadeira_pav * pavimentos
    pingadeira_total = pingadeira_bloco * blocos

    # I17: fachada de um bloco, descontando esquadrias.
    area_fachada_bloco = (
        (peri_ext_bloco * (pe_direito + ACRESCIMO_LAJE_FACHADA_M) * pavimentos)
        + (peri_plat_bloco * alt_plat)
        - (esq_area_pav * pavimentos)
    )
    if area_fachada_bloco < 0:
        area_fachada_bloco = 0.0
    area_fachada_total = area_fachada_bloco * blocos

    area_cobertura_bloco = area_const
    area_cobertura_total = area_const * blocos

    area_alvenaria_hall_bloco = pavimentos * peri_hall_parede_pav * pe_direito
    area_alvenaria_hall_total = area_alvenaria_hall_bloco * blocos

    def pct(chave: str) -> float:
        return numero((percentuais or {}).get(chave), percentual=True) / 100.0

    q: dict = {
        "qtd_blocos": blocos,
        "qtd_pavimentos": pavimentos,
        "qtd_aptos_por_pavimento": aptos_pav,
        "qtd_aptos_por_bloco": aptos_bloco,
        "qtd_aptos_total": aptos_total,
        "area_construida_m2": area_const,
        "qtd_aguas_telhado": aguas,
        "perimetro_beiral_m": beiral,
        "perimetro_paredes_externas_bloco_m": peri_ext_bloco,
        "perimetro_paredes_externas_total_m": peri_ext_total,
        "perimetro_platibanda_bloco_m": peri_plat_bloco,
        "perimetro_platibanda_total_m": peri_plat_total,
        "perimetro_hall_parede_pav_m": peri_hall_parede_pav,
        "perimetro_hall_parede_total_m": peri_hall_parede_total,
        "perimetro_hall_rodape_pav_m": peri_hall_rodape_pav,
        "perimetro_hall_rodape_total_m": peri_hall_rodape_total,
        "area_laje_hall_pav_m2": area_laje_pav,
        "area_laje_hall_total_m2": area_laje_total,
        "area_piso_hall_pav_m2": area_piso_pav,
        "area_piso_hall_total_m2": area_piso_total,
        "pe_direito_m": pe_direito,
        "altura_platibanda_m": alt_plat,
        "caixas_inspecao_bloco": cx_insp_bloco,
        "caixas_inspecao_total": cx_insp_total,
        "caixas_gordura_bloco": cx_gord_bloco,
        "caixas_gordura_total": cx_gord_total,
        "esquadria_qtd_pav": esq_qtd_pav,
        "esquadria_perimetro_pav_m": esq_perimetro_pav,
        "esquadria_pingadeira_pav_m": esq_pingadeira_pav,
        "esquadria_area_pav_m2": esq_area_pav,
        "esquadria_area_total_m2": esq_area_total,
        "pingadeira_bloco_m": pingadeira_bloco,
        "pingadeira_total_m": pingadeira_total,
        "area_fachada_bloco_m2": area_fachada_bloco,
        "area_fachada_total_m2": area_fachada_total,
        "area_cobertura_bloco_m2": area_cobertura_bloco,
        "area_cobertura_total_m2": area_cobertura_total,
        "area_alvenaria_hall_bloco_m2": area_alvenaria_hall_bloco,
        "area_alvenaria_hall_total_m2": area_alvenaria_hall_total,
        "pct_troca_revestimento_fachada_m2": pct("troca_revestimento_fachada")
        * area_fachada_total,
        "pct_troca_revestimento_paredes_hall_m2": pct("troca_revestimento_paredes_hall")
        * area_alvenaria_hall_total,
        "pct_troca_revestimento_tetos_hall_m2": pct("troca_revestimento_tetos_hall")
        * area_laje_total,
        "pct_troca_pisos_hall_m2": pct("troca_pisos_hall") * area_piso_total,
        "pct_troca_rodape_hall_m": pct("troca_rodape_hall") * peri_hall_rodape_total,
        "pct_troca_estrutura_cobertura_m2": pct("troca_estrutura_cobertura")
        * area_cobertura_total,
        "pct_instalacao_tabeira_beiral_m": pct("instalacao_tabeira_beiral")
        * peri_ext_total,
        "pct_troca_telhas_cobertura_m2": pct("troca_telhas_cobertura") * area_cobertura_total,
        "pct_troca_rufos_pingadeira_m": pct("troca_rufos_pingadeira") * peri_plat_total,
        "pct_pintura_fachada_m2": pct("pintura_fachada") * area_fachada_total,
        "pct_pintura_paredes_hall_m2": pct("pintura_paredes_hall") * area_alvenaria_hall_total,
        "pct_pintura_teto_hall_m2": pct("pintura_teto_hall") * area_laje_total,
    }
    q["esquadrias"] = linhas_esq
    return q
