"""Carrega ícones SVG de assets/icons para uso em widgets Tkinter."""

from __future__ import annotations

import tkinter as tk

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


def _aplicar_cor_svg(svg_texto: str, cor: str) -> str:
    svg_texto = svg_texto.replace('stroke="currentColor"', f'stroke="{cor}"')
    svg_texto = svg_texto.replace('fill="currentColor"', f'fill="{cor}"')
    if 'fill="none"' not in svg_texto and f'fill="{cor}"' not in svg_texto:
        svg_texto = svg_texto.replace("<path ", f'<path fill="{cor}" ')
    return svg_texto
