"""Edição do desenho do ORCCAD: seleção, mover, apagar, cotas e histórico.

As camadas seguem o formato do painel: {nome: {"pontos": [Ponto], "fechado": bool}}.
Uma "linha" é o segmento i da camada, entre pontos[i] e pontos[(i + 1) % n].
"""

from __future__ import annotations

from typing import Iterable, Sequence

from core.desenho_geometria import Ponto, unidade_direcao

Camadas = dict[str, dict]
Selecao = set[tuple[str, int]]


def indices_segmentos(n: int, fechado: bool) -> range:
    if n < 2:
        return range(0)
    return range(n if fechado and n >= 3 else n - 1)


def extremos_segmento(n: int, indice: int) -> tuple[int, int]:
    return indice, (indice + 1) % n


def segmento_dentro_retangulo(
    a: Ponto, b: Ponto, minx: float, miny: float, maxx: float, maxy: float
) -> bool:
    """Seleção por janela (esquerda → direita): a linha inteira dentro."""
    return all(minx <= p.x <= maxx and miny <= p.y <= maxy for p in (a, b))


def segmento_cruza_retangulo(
    a: Ponto, b: Ponto, minx: float, miny: float, maxx: float, maxy: float
) -> bool:
    """Seleção por cruzamento (direita → esquerda): a linha toca o retângulo."""
    dx, dy = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, a.x - minx),
        (dx, maxx - a.x),
        (-dy, a.y - miny),
        (dy, maxy - a.y),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def selecionar_por_retangulo(
    camadas: Camadas,
    canto_a: Ponto,
    canto_b: Ponto,
    *,
    cruzamento: bool,
) -> Selecao:
    minx, maxx = sorted((canto_a.x, canto_b.x))
    miny, maxy = sorted((canto_a.y, canto_b.y))
    teste = segmento_cruza_retangulo if cruzamento else segmento_dentro_retangulo
    saida: Selecao = set()
    for nome, dados in camadas.items():
        pts = dados["pontos"]
        n = len(pts)
        for i in indices_segmentos(n, bool(dados["fechado"])):
            ia, ib = extremos_segmento(n, i)
            if teste(pts[ia], pts[ib], minx, miny, maxx, maxy):
                saida.add((nome, i))
    return saida


def vertices_da_selecao(camadas: Camadas, selecao: Iterable[tuple[str, int]]) -> set[tuple[str, int]]:
    saida: set[tuple[str, int]] = set()
    for nome, i in selecao:
        n = len(camadas[nome]["pontos"])
        if n < 2:
            continue
        ia, ib = extremos_segmento(n, i)
        saida.add((nome, ia))
        saida.add((nome, ib))
    return saida


def copiar_camadas(camadas: Camadas) -> Camadas:
    return {
        nome: {"pontos": list(dados["pontos"]), "fechado": bool(dados["fechado"])}
        for nome, dados in camadas.items()
    }


def mover_vertices(
    camadas: Camadas, vertices: Iterable[tuple[str, int]], dx: float, dy: float
) -> Camadas:
    """Desloca só os vértices indicados; as linhas vizinhas esticam (STRETCH)."""
    nova = copiar_camadas(camadas)
    for nome, idx in vertices:
        pts = nova[nome]["pontos"]
        p = pts[idx]
        pts[idx] = Ponto(p.x + dx, p.y + dy)
    return nova


def apagar_segmentos(
    pontos: Sequence[Ponto], fechado: bool, indices: Iterable[int]
) -> tuple[list[Ponto], bool] | None:
    """Remove linhas da camada. Devolve None se sobrarem trechos separados."""
    n = len(pontos)
    todos = list(indices_segmentos(n, fechado))
    apagar = {i for i in indices if i in todos}
    if not apagar:
        return list(pontos), fechado
    if len(apagar) == len(todos):
        return [], False
    if fechado and n >= 3:
        inicio = (min(apagar) + 1) % n
        ordem = [(inicio + k) % n for k in range(n)]
    else:
        ordem = list(range(len(todos)))
    trechos: list[list[int]] = []
    atual: list[int] = []
    for i in ordem:
        if i in apagar:
            if atual:
                trechos.append(atual)
                atual = []
        else:
            atual.append(i)
    if atual:
        trechos.append(atual)
    if len(trechos) != 1:
        return None
    trecho = trechos[0]
    idx = [trecho[0]] + [(i + 1) % n for i in trecho]
    return [pontos[i] for i in idx], False


def ajustar_comprimento(
    pontos: Sequence[Ponto], fechado: bool, indice: int, comprimento: float
) -> list[Ponto]:
    """Muda o comprimento da linha `indice` mantendo o ponto inicial fixo.

    A linha seguinte é transladada junto (continua paralela e do mesmo tamanho),
    e a próxima absorve a diferença — num retângulo, ele apenas cresce/encolhe.
    """
    n = len(pontos)
    pts = list(pontos)
    ia, ib = extremos_segmento(n, indice)
    a, b = pts[ia], pts[ib]
    u = unidade_direcao(a, b)
    novo_b = Ponto(a.x + u.x * comprimento, a.y + u.y * comprimento)
    dx, dy = novo_b.x - b.x, novo_b.y - b.y
    pts[ib] = novo_b
    tem_proximo = fechado or ib + 1 < n
    ic = (ib + 1) % n
    if tem_proximo and ic != ia:
        c = pts[ic]
        pts[ic] = Ponto(c.x + dx, c.y + dy)
    return pts


class HistoricoDesenho:
    """Pilhas de desfazer/refazer com fotografias completas do desenho."""

    def __init__(self, limite: int = 200):
        self._limite = limite
        self._desfazer: list = []
        self._refazer: list = []

    def limpar(self):
        self._desfazer.clear()
        self._refazer.clear()

    def registrar(self, estado):
        self._desfazer.append(estado)
        if len(self._desfazer) > self._limite:
            del self._desfazer[0]
        self._refazer.clear()

    def pode_desfazer(self) -> bool:
        return bool(self._desfazer)

    def pode_refazer(self) -> bool:
        return bool(self._refazer)

    def desfazer(self, atual):
        if not self._desfazer:
            return None
        self._refazer.append(atual)
        return self._desfazer.pop()

    def refazer(self, atual):
        if not self._refazer:
            return None
        self._desfazer.append(atual)
        return self._refazer.pop()
