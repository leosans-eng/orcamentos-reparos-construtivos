"""Pré-carrega catálogos compartilhados da API em segundo plano."""

from __future__ import annotations

import threading


def iniciar_precarga_catalogos() -> None:
    def trabalho():
        try:
            from core.composicoes_proprias_storage import carregar as carregar_composicoes
            from core.etapas_predefinidas_storage import carregar as carregar_etapas

            carregar_composicoes()
            carregar_etapas()
        except ValueError:
            pass

    threading.Thread(target=trabalho, daemon=True).start()
