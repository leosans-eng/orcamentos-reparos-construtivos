"""Geometria e snap estilo CAD para o desenho de metragens.

Unidades internas: metros. A conversão para pixels fica na camada de interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin
from typing import Sequence

EPSILON = 1e-9

# Prioridade no estilo AutoCAD: extremidade vence meio, que vence perpendicular, etc.
_PRIORIDADE = {
    "primeiro": 0,
    "fim": 1,
    "int": 2,
    "meio": 3,
    "perp": 4,
    "igual": 5,
    "guia": 6,
    "orto": 7,
    "polar": 8,
    "grade": 9,
    "livre": 10,
}

ROTULO_SNAP = {
    "primeiro": "Completar",
    "fim": "Fim",
    "int": "Int",
    "meio": "Meio",
    "perp": "Perp",
    "igual": "Igual",
    "guia": "Guia",
    "orto": "Orto",
    "polar": "Polar",
    "grade": "Grade",
    "livre": "",
}

ANGULOS_ORTO = (0.0, 90.0, 180.0, 270.0)
ANGULOS_POLAR = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)


@dataclass(frozen=True)
class Ponto:
    x: float
    y: float


@dataclass(frozen=True)
class ConfigSnap:
    ortho: bool = False
    polar: bool = True
    trava_orto: bool = False
    osnap: bool = True
    grade: bool = True
    passo_grade: float = 0.1
    guias: bool = True


@dataclass(frozen=True)
class ResultadoSnap:
    ponto: Ponto
    tipo: str
    ancoras_guia: tuple[Ponto, ...] = ()

    @property
    def rotulo(self) -> str:
        return ROTULO_SNAP.get(self.tipo, "")


@dataclass(frozen=True)
class ResultadoDesenho:
    pontos_m: tuple[Ponto, ...]
    area_m2: float
    perimetro_m: float
    comprimento_m: float
    fechado: bool

    def valor_para(self, tipo_campo: str) -> float:
        """tipo_campo: 'area' ou 'perimetro'."""
        if tipo_campo == "area":
            return self.area_m2
        return self.perimetro_m


def distancia(a: Ponto, b: Ponto) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def quase_iguais(a: Ponto, b: Ponto, eps: float = 1e-7) -> bool:
    return distancia(a, b) <= eps


def angulo_graus(origem: Ponto, destino: Ponto) -> float:
    """Ângulo em graus, 0° = leste, sentido anti-horário (Y para cima)."""
    return (degrees(atan2(destino.y - origem.y, destino.x - origem.x)) + 360.0) % 360.0


def ponto_na_direcao(origem: Ponto, destino: Ponto, comprimento: float) -> Ponto:
    dx = destino.x - origem.x
    dy = destino.y - origem.y
    d = hypot(dx, dy)
    if d < EPSILON:
        return origem
    f = comprimento / d
    return Ponto(origem.x + dx * f, origem.y + dy * f)


def projetar_orto(origem: Ponto, cursor: Ponto) -> Ponto:
    if abs(cursor.x - origem.x) >= abs(cursor.y - origem.y):
        return Ponto(cursor.x, origem.y)
    return Ponto(origem.x, cursor.y)


def projetar_polar(origem: Ponto, cursor: Ponto, passo_graus: float = 45.0) -> Ponto:
    dx = cursor.x - origem.x
    dy = cursor.y - origem.y
    if hypot(dx, dy) < EPSILON or passo_graus <= 0:
        return Ponto(origem.x, origem.y)
    passo = radians(passo_graus)
    angulo = round(atan2(dy, dx) / passo) * passo
    ux, uy = cos(angulo), sin(angulo)
    proj = dx * ux + dy * uy
    return Ponto(origem.x + proj * ux, origem.y + proj * uy)


def assistir_angulo(
    origem: Ponto,
    cursor: Ponto,
    angulos: Sequence[float],
    abertura_m: float,
    *,
    dist_min: float = 0.2,
) -> Ponto | None:
    """Se o cursor estiver perto de um ângulo típico, projeta nele; senão None (livre)."""
    dx = cursor.x - origem.x
    dy = cursor.y - origem.y
    dist = hypot(dx, dy)
    if dist < dist_min or abertura_m <= 0:
        return None
    melhor: tuple[float, Ponto] | None = None
    for graus in angulos:
        rad = radians(graus)
        ux, uy = cos(rad), sin(rad)
        proj = dx * ux + dy * uy
        if proj < 0:
            continue
        alvo = Ponto(origem.x + proj * ux, origem.y + proj * uy)
        perp = hypot(cursor.x - alvo.x, cursor.y - alvo.y)
        if perp <= abertura_m and (melhor is None or perp < melhor[0]):
            melhor = (perp, alvo)
    return None if melhor is None else melhor[1]


def snap_grade(ponto: Ponto, passo: float) -> Ponto:
    if passo <= 0:
        return ponto
    return Ponto(round(ponto.x / passo) * passo, round(ponto.y / passo) * passo)


def passo_grade_visivel(px_por_metro: float, alvo_px: float = 32.0) -> float:
    if px_por_metro <= 0:
        return 1.0
    for passo in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0):
        if passo * px_por_metro >= alvo_px:
            return passo
    return 50.0


def ponto_no_segmento(p: Ponto, a: Ponto, b: Ponto) -> Ponto:
    dx, dy = b.x - a.x, b.y - a.y
    compr2 = dx * dx + dy * dy
    if compr2 < EPSILON:
        return a
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / compr2
    t = max(0.0, min(1.0, t))
    return Ponto(a.x + t * dx, a.y + t * dy)


def pe_perpendicular(p: Ponto, a: Ponto, b: Ponto) -> Ponto | None:
    dx, dy = b.x - a.x, b.y - a.y
    compr2 = dx * dx + dy * dy
    if compr2 < EPSILON:
        return None
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / compr2
    if t < 0.0 or t > 1.0:
        return None
    pe = Ponto(a.x + t * dx, a.y + t * dy)
    if quase_iguais(pe, a) or quase_iguais(pe, b) or quase_iguais(pe, p):
        return None
    return pe


def intersecao_segmentos(a1: Ponto, a2: Ponto, b1: Ponto, b2: Ponto) -> Ponto | None:
    den = (a1.x - a2.x) * (b1.y - b2.y) - (a1.y - a2.y) * (b1.x - b2.x)
    if abs(den) < EPSILON:
        return None
    t = ((a1.x - b1.x) * (b1.y - b2.y) - (a1.y - b1.y) * (b1.x - b2.x)) / den
    u = -((a1.x - a2.x) * (a1.y - b1.y) - (a1.y - a2.y) * (a1.x - b1.x)) / den
    if t < 0.0 or t > 1.0 or u < 0.0 or u > 1.0:
        return None
    ponto = Ponto(a1.x + t * (a2.x - a1.x), a1.y + t * (a2.y - a1.y))
    for extremo in (a1, a2, b1, b2):
        if quase_iguais(ponto, extremo):
            return None
    return ponto


def perimetro(pontos: Sequence[Ponto], *, fechado: bool) -> float:
    n = len(pontos)
    if n < 2:
        return 0.0
    total = 0.0
    trechos = n if fechado else n - 1
    for i in range(trechos):
        total += distancia(pontos[i], pontos[(i + 1) % n])
    return total


def area_poligono(pontos: Sequence[Ponto]) -> float:
    n = len(pontos)
    if n < 3:
        return 0.0
    soma = 0.0
    for i in range(n):
        x1, y1 = pontos[i].x, pontos[i].y
        x2, y2 = pontos[(i + 1) % n].x, pontos[(i + 1) % n].y
        soma += x1 * y2 - x2 * y1
    return abs(soma) / 2.0


def resultado_desenho(pontos: Sequence[Ponto], *, fechado: bool) -> ResultadoDesenho:
    pts = tuple(pontos)
    fechado_ok = bool(fechado and len(pts) >= 3)
    peri = perimetro(pts, fechado=fechado_ok)
    area = area_poligono(pts) if fechado_ok else 0.0
    return ResultadoDesenho(
        pontos_m=pts,
        area_m2=area,
        perimetro_m=peri,
        comprimento_m=peri,
        fechado=fechado_ok,
    )


def retangulo_eixos(a: Ponto, b: Ponto) -> tuple[Ponto, ...]:
    return (
        Ponto(a.x, a.y),
        Ponto(b.x, a.y),
        Ponto(b.x, b.y),
        Ponto(a.x, b.y),
    )


def _considerar(
    candidatos: list,
    ponto: Ponto,
    tipo: str,
    cursor: Ponto,
    constrained: Ponto,
    abertura: float,
    ancoras: tuple[Ponto, ...] = (),
) -> None:
    d = min(distancia(ponto, cursor), distancia(ponto, constrained))
    if d <= abertura:
        candidatos.append((_PRIORIDADE[tipo], d, ResultadoSnap(ponto, tipo, ancoras)))


def _angulos_assistencia(config: ConfigSnap) -> tuple[float, ...]:
    if config.polar:
        return ANGULOS_POLAR
    if config.ortho:
        return ANGULOS_ORTO
    return ()


def resolver_snap(
    cursor: Ponto,
    *,
    origem: Ponto | None,
    vertices: Sequence[Ponto],
    segmentos: Sequence[tuple[Ponto, Ponto]],
    config: ConfigSnap,
    abertura: float,
    abertura_guia: float | None = None,
    pode_fechar: bool = False,
    ponto_fechamento: Ponto | None = None,
) -> ResultadoSnap:
    """Resolve assistência de ângulo, osnap, guias e grade.

    Orto/Polar puxam o cursor para 90°/45° só quando ele já está perto desses
    eixos; caso contrário o traço permanece livre.
    """
    abertura = max(abertura, EPSILON)
    ab_guia = max(
        abertura_guia if abertura_guia is not None else abertura * 2.4,
        abertura,
    )
    constrained = cursor
    tipo_base = "livre"
    if origem is not None:
        if config.trava_orto:
            constrained = projetar_orto(origem, cursor)
            tipo_base = "orto"
        else:
            angulos = _angulos_assistencia(config)
            if angulos:
                assistido = assistir_angulo(origem, cursor, angulos, abertura)
                if assistido is not None:
                    constrained = assistido
                    tipo_base = "polar" if config.polar else "orto"

    candidatos: list[tuple[int, float, ResultadoSnap]] = []

    if config.osnap:
        for v in vertices:
            if origem is not None and quase_iguais(v, origem):
                continue
            if (
                pode_fechar
                and ponto_fechamento is not None
                and quase_iguais(v, ponto_fechamento)
            ):
                _considerar(
                    candidatos, v, "primeiro", cursor, constrained, abertura * 1.4
                )
            else:
                _considerar(candidatos, v, "fim", cursor, constrained, abertura)

        for a, b in segmentos:
            meio = Ponto((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)
            _considerar(candidatos, meio, "meio", cursor, constrained, abertura * 0.9)
            if origem is not None:
                pe = pe_perpendicular(origem, a, b)
                if pe is not None:
                    _considerar(
                        candidatos, pe, "perp", cursor, constrained, abertura * 0.9
                    )

        segs = list(segmentos)
        for i, (a1, a2) in enumerate(segs):
            for b1, b2 in segs[i + 1 :]:
                inter = intersecao_segmentos(a1, a2, b1, b2)
                if inter is not None:
                    _considerar(
                        candidatos, inter, "int", cursor, constrained, abertura * 0.9
                    )

    if config.guias:
        verts = [
            v
            for v in vertices
            if origem is None or not quase_iguais(v, origem)
        ]
        for v in verts:
            if abs(cursor.y - v.y) <= ab_guia or abs(constrained.y - v.y) <= ab_guia:
                _considerar(
                    candidatos,
                    Ponto(cursor.x, v.y),
                    "guia",
                    cursor,
                    constrained,
                    ab_guia,
                    (v,),
                )
                _considerar(
                    candidatos,
                    Ponto(constrained.x, v.y),
                    "guia",
                    cursor,
                    constrained,
                    ab_guia,
                    (v,),
                )
            if abs(cursor.x - v.x) <= ab_guia or abs(constrained.x - v.x) <= ab_guia:
                _considerar(
                    candidatos,
                    Ponto(v.x, cursor.y),
                    "guia",
                    cursor,
                    constrained,
                    ab_guia,
                    (v,),
                )
                _considerar(
                    candidatos,
                    Ponto(v.x, constrained.y),
                    "guia",
                    cursor,
                    constrained,
                    ab_guia,
                    (v,),
                )
        for vx in verts:
            for vy in verts:
                _considerar(
                    candidatos,
                    Ponto(vx.x, vy.y),
                    "guia",
                    cursor,
                    constrained,
                    ab_guia,
                    (vx, vy),
                )

        if origem is not None:
            direcao = constrained
            compr_atual = distancia(origem, direcao)
            if compr_atual > EPSILON:
                for a, b in segmentos:
                    comprimento = distancia(a, b)
                    if comprimento < EPSILON:
                        continue
                    if abs(compr_atual - comprimento) <= ab_guia:
                        alvo = ponto_na_direcao(origem, direcao, comprimento)
                        _considerar(
                            candidatos,
                            alvo,
                            "igual",
                            cursor,
                            constrained,
                            ab_guia,
                            (a, b),
                        )

    if candidatos:
        candidatos.sort(key=lambda item: (item[0], item[1]))
        return candidatos[0][2]

    ponto = constrained
    tipo = tipo_base
    if config.grade and config.passo_grade > 0:
        grade = snap_grade(ponto, config.passo_grade)
        if not quase_iguais(grade, ponto):
            return ResultadoSnap(grade, "grade")
        ponto = grade
    return ResultadoSnap(ponto, tipo)


def desenho_para_dict(pontos: Sequence[Ponto], *, fechado: bool) -> dict:
    pts = list(pontos or [])
    return {
        "pontos": [{"x": float(p.x), "y": float(p.y)} for p in pts],
        "fechado": bool(fechado) and len(pts) >= 3,
    }


def dict_para_pontos(dados) -> tuple[list[Ponto], bool]:
    if not isinstance(dados, dict):
        return [], False
    pontos: list[Ponto] = []
    for item in dados.get("pontos") or []:
        if not isinstance(item, dict):
            continue
        try:
            pontos.append(Ponto(float(item["x"]), float(item["y"])))
        except (KeyError, TypeError, ValueError):
            continue
    fechado = bool(dados.get("fechado")) and len(pontos) >= 3
    return pontos, fechado
