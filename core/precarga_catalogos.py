"""Pré-carrega catálogos compartilhados da API em segundo plano."""

from __future__ import annotations

import threading


def iniciar_precarga_catalogos() -> None:
    def trabalho():
        try:
            from core.composicoes_proprias_storage import carregar as carregar_composicoes
            from core.etapas_predefinidas_storage import carregar as carregar_etapas
            from core.orcamento_storage import listar_orcamentos_resumo

            carregar_composicoes()
            carregar_etapas()
            listar_orcamentos_resumo()
        except ValueError:
            pass

    threading.Thread(target=trabalho, daemon=True).start()
