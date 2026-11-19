"""Descobre os cômodos de uma planta a partir das linhas desenhadas.

Ideia geral (o mesmo que faríamos no papel):
1. Junta todas as linhas (contorno externo + paredes internas).
2. Pontas de parede que ficaram "quase" encostadas em outra linha são
   encostadas de verdade (folga de até TOLERANCIA_M).
3. Corta as linhas onde elas se cruzam ou se tocam.
4. Descarta pontas soltas (paredes que não fecham nada).
5. Percorre as linhas sempre virando para o mesmo lado: cada volta fechada
   é um cômodo. A volta por fora de tudo (área negativa) é descartada.
6. Desconta "ilhas" (ex.: um armário desenhado solto dentro de um quarto).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2
from typing import Sequence

from core.desenho_geometria import (
    Ponto,
    distancia,
    normal_esquerda,
    ponto_no_segmento,
    unidade_direcao,
)

TOLERANCIA_M = 0.10  # folga corrigida entre a ponta de uma parede e outra linha
AREA_MINIMA_M2 = 0.05  # voltas menores que isso são sobras de desenho
_CASAS = 6  # pontos a menos de 1 µm são o mesmo ponto


@dataclass(frozen=True)
class Comodo:
    nome: str
    pontos: tuple[Ponto, ...]
    area_m2: float
    perimetro_m: float
    rotulo: Ponto  # onde escrever o nome no desenho
    furos: tuple[tuple[Ponto, ...], ...] = ()  # ilhas descontadas (sentido horário)
    # Medidas úteis (descontando a espessura das paredes); None = não calculado.
    area_util_m2: float | None = None
    perimetro_util_m: float | None = None
    poligono_util: tuple[Ponto, ...] = ()

    @property
    def area_exibida(self) -> float:
        return self.area_util_m2 if self.area_util_m2 is not None else self.area_m2

    @property
    def perimetro_exibido(self) -> float:
        return (
            self.perimetro_util_m if self.perimetro_util_m is not None else self.perimetro_m
        )


def detectar_comodos(
    linhas: Sequence[tuple[Sequence[Ponto], bool]],
    *,
    tolerancia: float = TOLERANCIA_M,
) -> list[Comodo]:
    """`linhas`: lista de (pontos, fechado). Devolve os cômodos encontrados."""
    polilinhas = [
        (list(pts), bool(fechado) and len(pts) >= 3)
        for pts, fechado in linhas
        if len(pts) >= 2
    ]
    if not polilinhas:
        return []
    _encostar_pontas(polilinhas, tolerancia)

    segmentos: list[tuple[Ponto, Ponto]] = []
    for pts, fechado in polilinhas:
        segmentos.extend(_pares(pts, fechado))
    segmentos = [(a, b) for a, b in segmentos if distancia(a, b) > 1e-9]

    vizinhos = _grafo(_cortar(segmentos))
    _podar_pontas(vizinhos)
    if not vizinhos:
        return []

    faces = _faces(vizinhos)
    componente = _componentes(vizinhos)

    internas = []  # (pontos, area, componente)
    externas = []  # contorno de fora de cada componente (área negativa)
    for face in faces:
        area = _area_com_sinal(face)
        comp = componente[_chave(face[0])]
        if area > AREA_MINIMA_M2:
            internas.append((face, area, comp))
        elif area < -AREA_MINIMA_M2:
            externas.append((face, -area, comp))

    # Ilhas: o contorno de fora de um conjunto solto, dentro de um cômodo,
    # é descontado do menor cômodo que o contém.
    furos: dict[int, list[list[Ponto]]] = {}
    for contorno, _area, comp in externas:
        dono = None
        for i, (face, area, comp_face) in enumerate(internas):
            if comp_face == comp:
                continue
            if all(_dentro(p, face) for p in contorno):
                if dono is None or area < internas[dono][1]:
                    dono = i
        if dono is not None:
            furos.setdefault(dono, []).append(contorno)

    brutos = []
    for i, (face, area, _comp) in enumerate(internas):
        buracos = furos.get(i, [])
        area_final = area - sum(abs(_area_com_sinal(b)) for b in buracos)
        if area_final <= AREA_MINIMA_M2:
            continue
        perim = _perimetro(face) + sum(_perimetro(b) for b in buracos)
        rotulo = _ponto_para_rotulo(face, buracos)
        brutos.append((face, area_final, perim, rotulo, buracos))

    # Numeração estável: de cima para baixo, da esquerda para a direita.
    brutos.sort(key=lambda item: (-round(item[3].y, 2), round(item[3].x, 2)))
    return [
        Comodo(
            nome=f"Cômodo {n}",
            pontos=tuple(face),
            area_m2=area,
            perimetro_m=perim,
            rotulo=rotulo,
            furos=tuple(tuple(b) for b in buracos),
        )
        for n, (face, area, perim, rotulo, buracos) in enumerate(brutos, start=1)
    ]


def ponto_dentro(p: Ponto, comodo: Comodo) -> bool:
    """O ponto está no cômodo (e fora das ilhas dele)?"""
    return _dentro(p, comodo.pontos) and not any(_dentro(p, f) for f in comodo.furos)


def medidas_uteis(
    comodo: Comodo,
    segmentos_externa: Sequence[tuple[Ponto, Ponto]],
    espessura: float,
) -> tuple[float, float, tuple[Ponto, ...]] | None:
    """Área, perímetro e contorno do cômodo descontando as paredes.

    A linha EXTERNA é a face de fora do prédio: a parede inteira fica para
    dentro. Paredes internas são desenhadas pelo eixo: metade para cada lado.
    Devolve None se o cômodo for estreito demais para a espessura.
    """
    if espessura <= 0:
        return comodo.area_m2, comodo.perimetro_m, comodo.pontos
    face = list(comodo.pontos)
    recuos = []
    for i, a in enumerate(face):
        b = face[(i + 1) % len(face)]
        na_externa = any(
            distancia(a, ponto_no_segmento(a, c, d)) < 1e-6
            and distancia(b, ponto_no_segmento(b, c, d)) < 1e-6
            for c, d in segmentos_externa
        )
        recuos.append(espessura if na_externa else espessura / 2.0)
    util = _recuar(face, recuos)
    if util is None:
        return None
    area = _area_com_sinal(util)
    perim = _perimetro(util)
    for furo in comodo.furos:
        # Ilha: a parede em volta dela cresce para fora (metade da espessura).
        anti = list(reversed(furo))
        maior = _recuar(anti, [-espessura / 2.0] * len(anti))
        if maior is None:
            continue
        area -= _area_com_sinal(maior)
        perim += _perimetro(maior)
    if area <= 0:
        return None
    return area, perim, tuple(util)


def _recuar(pts: list[Ponto], recuos: list[float]) -> list[Ponto] | None:
    """Desloca cada lado do polígono (anti-horário) para dentro pelo seu recuo."""
    n = len(pts)
    linhas = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        nrm = normal_esquerda(a, b)
        d = recuos[i]
        linhas.append(
            (Ponto(a.x + nrm.x * d, a.y + nrm.y * d), unidade_direcao(a, b), nrm, d)
        )
    novos = []
    for i in range(n):
        p1, u1, _n1, _d1 = linhas[i - 1]
        p2, u2, n2, d2 = linhas[i]
        den = u1.x * u2.y - u1.y * u2.x
        if abs(den) < 1e-12:
            # Lados alinhados (ex.: parede encontrando no meio): só desloca.
            novos.append(Ponto(pts[i].x + n2.x * d2, pts[i].y + n2.y * d2))
            continue
        qx, qy = p2.x - p1.x, p2.y - p1.y
        t = (qx * u2.y - qy * u2.x) / den
        novos.append(Ponto(p1.x + t * u1.x, p1.y + t * u1.y))
    # Se algum lado inverteu de sentido, o cômodo "sumiu" com a espessura.
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        a2, b2 = novos[i], novos[(i + 1) % n]
        if (b.x - a.x) * (b2.x - a2.x) + (b.y - a.y) * (b2.y - a2.y) <= 0:
            return None
    if _area_com_sinal(novos) <= 1e-9:
        return None
    return novos


# ---------------------------------------------------------------- etapas


def _pares(pts: list[Ponto], fechado: bool) -> list[tuple[Ponto, Ponto]]:
    saida = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if fechado:
        saida.append((pts[-1], pts[0]))
    return saida


def _encostar_pontas(polilinhas, tolerancia: float) -> None:
    """Pontas de linhas abertas perto de outra linha passam a tocá-la."""
    for indice, (pts, fechado) in enumerate(polilinhas):
        if fechado:
            continue
        for posicao in (0, len(pts) - 1):
            ponta = pts[posicao]
            vizinho = pts[1] if posicao == 0 else pts[-2]
            # 1º: um vértice próximo (canto); 2º: um ponto sobre uma linha.
            melhor = None
            for j, (outros, _f) in enumerate(polilinhas):
                for k, v in enumerate(outros):
                    if j == indice and k == posicao:
                        continue
                    d = distancia(ponta, v)
                    if 1e-9 < d <= tolerancia and (melhor is None or d < melhor[0]):
                        melhor = (d, v)
            if melhor is None:
                for j, (outros, fechado_j) in enumerate(polilinhas):
                    for a, b in _pares(outros, fechado_j):
                        # Não encosta na própria linha que sai desta ponta.
                        if j == indice and ponta in (a, b):
                            continue
                        pe = ponto_no_segmento(ponta, a, b)
                        d = distancia(ponta, pe)
                        if 1e-9 < d <= tolerancia and (melhor is None or d < melhor[0]):
                            melhor = (d, pe)
            if melhor is not None and not _mesmo(melhor[1], vizinho):
                pts[posicao] = melhor[1]


def _cortar(segmentos: list[tuple[Ponto, Ponto]]) -> list[tuple[Ponto, Ponto]]:
    """Divide cada linha onde outra linha a cruza ou encosta nela."""
    vertices = {p for seg in segmentos for p in seg}
    saida = []
    for i, (a, b) in enumerate(segmentos):
        cortes = {0.0, 1.0}
        for j, (c, d) in enumerate(segmentos):
            if i == j:
                continue
            t = _intersecao_t(a, b, c, d)
            if t is not None:
                cortes.add(t)
        for p in vertices:
            t = _parametro_sobre(p, a, b)
            if t is not None:
                cortes.add(t)
        ordem = sorted(cortes)
        pontos = [_em(a, b, t) for t in ordem]
        for p, q in zip(pontos, pontos[1:]):
            if distancia(p, q) > 1e-7:
                saida.append((p, q))
    return saida


def _grafo(segmentos) -> dict[tuple, set[tuple]]:
    vizinhos: dict[tuple, set[tuple]] = {}
    for a, b in segmentos:
        ka, kb = _chave(a), _chave(b)
        if ka == kb:
            continue
        vizinhos.setdefault(ka, set()).add(kb)
        vizinhos.setdefault(kb, set()).add(ka)
    return vizinhos


def _podar_pontas(vizinhos: dict[tuple, set[tuple]]) -> None:
    """Remove, em cadeia, os pontos ligados a uma linha só (pontas soltas)."""
    fila = [k for k, viz in vizinhos.items() if len(viz) < 2]
    while fila:
        k = fila.pop()
        if k not in vizinhos or len(vizinhos[k]) >= 2:
            continue
        for outro in vizinhos.pop(k):
            viz = vizinhos.get(outro)
            if viz is None:
                continue
            viz.discard(k)
            if len(viz) < 2:
                fila.append(outro)


def _faces(vizinhos: dict[tuple, set[tuple]]) -> list[list[Ponto]]:
    """Percorre cada lado de cada linha virando sempre o máximo à direita."""
    ordenados = {
        k: sorted(viz, key=lambda o, k=k: atan2(o[1] - k[1], o[0] - k[0]))
        for k, viz in vizinhos.items()
    }
    usados: set[tuple[tuple, tuple]] = set()
    faces = []
    for u, viz in ordenados.items():
        for v in viz:
            if (u, v) in usados:
                continue
            face = []
            a, b = u, v
            for _ in range(10000):
                if (a, b) in usados:
                    break
                usados.add((a, b))
                face.append(Ponto(*a))
                lista = ordenados[b]
                i = lista.index(a)
                a, b = b, lista[i - 1]  # vizinho anterior no sentido anti-horário
            if len(face) >= 3:
                faces.append(face)
    return faces


def _componentes(vizinhos: dict[tuple, set[tuple]]) -> dict[tuple, int]:
    comp: dict[tuple, int] = {}
    n = 0
    for inicio in vizinhos:
        if inicio in comp:
            continue
        pilha = [inicio]
        comp[inicio] = n
        while pilha:
            k = pilha.pop()
            for o in vizinhos[k]:
                if o not in comp:
                    comp[o] = n
                    pilha.append(o)
        n += 1
    return comp


# ---------------------------------------------------------------- auxiliares


def _chave(p) -> tuple[float, float]:
    if isinstance(p, Ponto):
        return (round(p.x, _CASAS) + 0.0, round(p.y, _CASAS) + 0.0)
    return p


def _mesmo(a: Ponto, b: Ponto) -> bool:
    return distancia(a, b) <= 1e-7


def _em(a: Ponto, b: Ponto, t: float) -> Ponto:
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    return Ponto(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y))


def _intersecao_t(a: Ponto, b: Ponto, c: Ponto, d: Ponto) -> float | None:
    """Parâmetro t (0..1) em a–b onde c–d cruza, contando as pontas."""
    rx, ry = b.x - a.x, b.y - a.y
    sx, sy = d.x - c.x, d.y - c.y
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    qx, qy = c.x - a.x, c.y - a.y
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    eps = 1e-9
    if -eps <= t <= 1 + eps and -eps <= u <= 1 + eps:
        return min(1.0, max(0.0, t))
    return None


def _parametro_sobre(p: Ponto, a: Ponto, b: Ponto) -> float | None:
    """t de p sobre a–b, se p estiver em cima da linha (fora das pontas)."""
    dx, dy = b.x - a.x, b.y - a.y
    compr2 = dx * dx + dy * dy
    if compr2 < 1e-18:
        return None
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / compr2
    if t <= 1e-9 or t >= 1 - 1e-9:
        return None
    pe = Ponto(a.x + t * dx, a.y + t * dy)
    if distancia(p, pe) > 1e-7:
        return None
    return t


def _area_com_sinal(pts: Sequence[Ponto]) -> float:
    soma = 0.0
    n = len(pts)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        soma += p.x * q.y - q.x * p.y
    return soma / 2.0


def _perimetro(pts: Sequence[Ponto]) -> float:
    n = len(pts)
    return sum(distancia(pts[i], pts[(i + 1) % n]) for i in range(n))


def _dentro(p: Ponto, poligono: Sequence[Ponto]) -> bool:
    dentro = False
    n = len(poligono)
    for i in range(n):
        a, b = poligono[i], poligono[(i + 1) % n]
        if (a.y > p.y) != (b.y > p.y):
            x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x > p.x:
                dentro = not dentro
    return dentro


def _ponto_para_rotulo(face: Sequence[Ponto], furos) -> Ponto:
    """Um ponto bem no meio da parte mais larga do cômodo."""
    ys = [p.y for p in face]
    y0, y1 = min(ys), max(ys)
    altura = y1 - y0
    contornos = [list(face)] + [list(f) for f in furos]
    melhor = None
    for fracao in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8):
        y = y0 + altura * fracao
        xs = []
        for contorno in contornos:
            n = len(contorno)
            for i in range(n):
                a, b = contorno[i], contorno[(i + 1) % n]
                if (a.y > y) != (b.y > y):
                    xs.append(a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y))
        xs.sort()
        for xa, xb in zip(xs[0::2], xs[1::2]):
            # Prefere a faixa mais larga, mas valoriza ficar perto do meio.
            nota = (xb - xa) * (1.0 - 0.6 * abs(fracao - 0.5))
            if melhor is None or nota > melhor[0]:
                melhor = (nota, Ponto((xa + xb) / 2.0, y))
    if melhor is not None:
        return melhor[1]
    n = len(face)
    return Ponto(sum(p.x for p in face) / n, sum(p.y for p in face) / n)

