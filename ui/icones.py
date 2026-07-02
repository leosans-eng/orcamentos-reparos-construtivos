"""Carrega ícones SVG de assets/icons para uso em widgets Tkinter."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from app_paths import asset_path

try:
    from tksvg import SvgImage
except ImportError:
    SvgImage = None  # type: ignore[misc, assignment]


def criar_icone_svg(
    master: tk.Misc,
    nome: str,
    *,
    altura: int,
    cor: str = "#006699",
) -> tk.PhotoImage:
    """Rasteriza um SVG de assets/icons/{nome}.svg na altura indicada (px)."""
    if SvgImage is None:
        raise ImportError("Pacote 'tksvg' não instalado. Execute: pip install tksvg")

    caminho = asset_path("icons", f"{nome}.svg")
    if caminho is None:
        raise FileNotFoundError(f"Ícone SVG não encontrado: assets/icons/{nome}.svg")

    svg_texto = caminho.read_text(encoding="utf-8")
    svg_texto = _aplicar_cor_svg(svg_texto, cor)

    return SvgImage(master=master, data=svg_texto, scaletoheight=altura)


def altura_icone_botao_compact(master: tk.Misc, estilo: str = "Compact.TButton") -> int:
    """Altura do ícone alinhada à fonte do botão, sem aumentar a altura do botão."""
    fonte = tkfont.Font(font=ttk.Style(master).lookup(estilo, "font"))
    return max(11, fonte.metrics("ascent") - 2)


def criar_botao_ttk_com_icone(
    parent: tk.Misc,
    *,
    texto: str,
    nome_icone: str,
    command,
    estilo: str = "Compact.TButton",
    cor_icone: str = "#000000",
    refs: list | None = None,
) -> ttk.Button:
    """Cria ttk.Button com ícone SVG à esquerda (compound=left)."""
    altura = altura_icone_botao_compact(parent, estilo)
    icone = criar_icone_svg(parent, nome_icone, altura=altura, cor=cor_icone)
    if refs is not None:
        refs.append(icone)
    return ttk.Button(
        parent,
        text=texto,
        image=icone,
        compound="left",
        command=command,
        style=estilo,
    )


def _aplicar_cor_svg(svg_texto: str, cor: str) -> str:
    svg_texto = svg_texto.replace('stroke="currentColor"', f'stroke="{cor}"')
    svg_texto = svg_texto.replace('fill="currentColor"', f'fill="{cor}"')
    if 'fill="none"' not in svg_texto and f'fill="{cor}"' not in svg_texto:
        svg_texto = svg_texto.replace("<path ", f'<path fill="{cor}" ')
    return svg_texto
