"""Persistência dos orçamentos customizados em arquivo JSON do usuário."""

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from app_paths import orcamentos_customizados_path

from core.orcamento_customizado import BDI_PADRAO, OrcamentoCustomizado

VERSAO_ARQUIVO = 1


def _agora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _novo_id():
    return str(uuid.uuid4())


def _orcamento_vazio_dict(nome="Novo orçamento"):
    orc = OrcamentoCustomizado(nome=nome)
    orc.id = _novo_id()
    dados = orc.exportar_dict()
    dados["estado_referencia"] = ""
    dados["atualizado_em"] = _agora_iso()
    return dados


def carregar_arquivo():
    caminho = orcamentos_customizados_path()
    if not caminho.is_file():
        orc = _orcamento_vazio_dict()
        dados = {
            "versao": VERSAO_ARQUIVO,
            "orcamento_ativo_id": orc["id"],
            "orcamentos": [orc],
        }
        salvar_arquivo(dados)
        return dados

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    if not dados.get("orcamentos"):
        orc = _orcamento_vazio_dict()
        dados = {
            "versao": VERSAO_ARQUIVO,
            "orcamento_ativo_id": orc["id"],
            "orcamentos": [orc],
        }
        salvar_arquivo(dados)
        return dados

    if not dados.get("orcamento_ativo_id"):
        dados["orcamento_ativo_id"] = dados["orcamentos"][0]["id"]

    return dados


def salvar_arquivo(dados):
    caminho = orcamentos_customizados_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def listar_nomes(dados):
    return [(o["id"], o.get("nome", "Sem nome")) for o in dados.get("orcamentos", [])]


def obter_orcamento_dict(dados, orcamento_id):
    for orc in dados.get("orcamentos", []):
        if orc.get("id") == orcamento_id:
            return deepcopy(orc)
    return None


def dict_para_orcamento(dados_orc):
    orc = OrcamentoCustomizado.importar_dict(dados_orc)
    orc.id = dados_orc.get("id", _novo_id())
    orc.estado_referencia = dados_orc.get("estado_referencia", "")
    return orc


def orcamento_para_dict(orcamento):
    dados = orcamento.exportar_dict()
    dados["id"] = getattr(orcamento, "id", _novo_id())
    dados["estado_referencia"] = getattr(orcamento, "estado_referencia", "")
    dados["atualizado_em"] = _agora_iso()
    return dados


def atualizar_orcamento_na_lista(dados, orcamento):
    payload = orcamento_para_dict(orcamento)
    encontrado = False
    for indice, orc in enumerate(dados.get("orcamentos", [])):
        if orc.get("id") == payload["id"]:
            dados["orcamentos"][indice] = payload
            encontrado = True
            break
    if not encontrado:
        dados.setdefault("orcamentos", []).append(payload)
    dados["orcamento_ativo_id"] = payload["id"]
    return dados


def criar_orcamento(dados, nome):
    orc = _orcamento_vazio_dict(nome.strip())
    dados.setdefault("orcamentos", []).append(orc)
    dados["orcamento_ativo_id"] = orc["id"]
    salvar_arquivo(dados)
    return orc["id"]


def renomear_orcamento(dados, orcamento_id, novo_nome):
    novo_nome = novo_nome.strip()
    if not novo_nome:
        raise ValueError("Informe o nome do orçamento.")
    for orc in dados.get("orcamentos", []):
        if orc.get("id") == orcamento_id:
            orc["nome"] = novo_nome
            orc["atualizado_em"] = _agora_iso()
            salvar_arquivo(dados)
            return
    raise ValueError("Orçamento não encontrado.")


def excluir_orcamento(dados, orcamento_id):
    orcamentos = dados.get("orcamentos", [])
    if len(orcamentos) <= 1:
        raise ValueError("Não é possível excluir o único orçamento.")
    restantes = [o for o in orcamentos if o.get("id") != orcamento_id]
    if len(restantes) == len(orcamentos):
        raise ValueError("Orçamento não encontrado.")
    dados["orcamentos"] = restantes
    if dados.get("orcamento_ativo_id") == orcamento_id:
        dados["orcamento_ativo_id"] = restantes[0]["id"]
    salvar_arquivo(dados)
    return dados["orcamento_ativo_id"]
