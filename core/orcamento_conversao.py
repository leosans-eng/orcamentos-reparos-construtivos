"""Conversão entre OrcamentoCustomizado e dicionários persistidos."""

import uuid

from core.orcamento_customizado import OrcamentoCustomizado


def novo_id():
    return str(uuid.uuid4())


def dict_para_orcamento(dados_orc):
    orc = OrcamentoCustomizado.importar_dict(dados_orc)
    orc.id = dados_orc.get("id", novo_id())
    orc.estado_referencia = dados_orc.get("estado_referencia", "")
    return orc


def orcamento_para_payload_api(orcamento) -> dict:
    return {
        "id": getattr(orcamento, "id", novo_id()),
        "nome": orcamento.nome,
        "bdi_percent": orcamento.bdi_percent,
        "estado_referencia": getattr(orcamento, "estado_referencia", ""),
        "grupos": orcamento.grupos,
    }
