"""Caminhos dos templates Word do formatador."""

from __future__ import annotations

from app_paths import app_dir, asset_path, bundle_dir


def caminho_modelo_word(nome_arquivo: str) -> str:
    caminho = asset_path("modelos", nome_arquivo)
    if caminho is not None:
        return str(caminho)

    for base in (bundle_dir(), app_dir()):
        candidato = base / "modelos" / nome_arquivo
        if candidato.is_file():
            return str(candidato)

    raise FileNotFoundError(
        f"Template Word não encontrado: {nome_arquivo}. "
        "Verifique assets/modelos/."
    )
