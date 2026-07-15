"""Substitui storages da API por leitura/gravação em JSON (modo offline)."""

from __future__ import annotations

import sys


def ativar_modo_offline() -> None:
    from core import (
        composicoes_proprias_storage_local,
        etapas_predefinidas_storage_local,
        orcamento_storage_local,
    )

    sys.modules["core.orcamento_storage"] = orcamento_storage_local
    sys.modules["core.composicoes_proprias_storage"] = composicoes_proprias_storage_local
    sys.modules["core.etapas_predefinidas_storage"] = etapas_predefinidas_storage_local
