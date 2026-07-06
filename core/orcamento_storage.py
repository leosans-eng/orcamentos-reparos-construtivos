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
    agora = _agora_iso()
    orc = OrcamentoCustomizado(nome=nome)
    orc.id = _novo_id()
    dados = orc.exportar_dict()
    dados["estado_referencia"] = ""
    dados["criado_em"] = agora
    dados["atualizado_em"] = agora
    return dados


def _arquivo_vazio():
    return {
        "versao": VERSAO_ARQUIVO,
        "orcamento_ativo_id": None,
        "orcamentos": [],
    }


def _normalizar_orcamentos(dados):
    alterado = False
    orcamentos = dados.get("orcamentos", [])
    for orc in orcamentos:
        if not orc.get("criado_em"):
            orc["criado_em"] = orc.get("atualizado_em") or _agora_iso()
            alterado = True
        if not orc.get("atualizado_em"):
            orc["atualizado_em"] = orc.get("criado_em") or _agora_iso()
            alterado = True
    return alterado


def carregar_arquivo():
    caminho = orcamentos_customizados_path()
    if not caminho.is_file():
        return _arquivo_vazio()

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    if not dados.get("orcamentos"):
        dados = _arquivo_vazio()
        return dados

    if _normalizar_orcamentos(dados):
        salvar_arquivo(dados)

    if dados.get("orcamento_ativo_id"):
        ativo = dados["orcamento_ativo_id"]
        if not obter_orcamento_dict(dados, ativo):
            dados["orcamento_ativo_id"] = dados["orcamentos"][0]["id"]

    return dados


def salvar_arquivo(dados):
    caminho = orcamentos_customizados_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def listar_nomes(dados):
    return [(o["id"], o.get("nome", "Sem nome")) for o in dados.get("orcamentos", [])]


def _contar_itens_orcamento(dados_orc):
    total = 0
    for grupo in dados_orc.get("grupos", []):
        total += len(grupo.get("itens", []))
    return len(dados_orc.get("grupos", [])), total


def listar_orcamentos_resumo(dados):
    """Lista orçamentos do mais novo ao mais antigo (por data de criação)."""
    resumos = []
    for orc in dados.get("orcamentos", []):
        grupos, itens = _contar_itens_orcamento(orc)
        resumos.append(
            {
                "id": orc["id"],
                "nome": orc.get("nome", "Sem nome"),
                "criado_em": orc.get("criado_em", ""),
                "atualizado_em": orc.get("atualizado_em", ""),
                "grupos": grupos,
                "itens": itens,
            }
        )
    resumos.sort(key=lambda item: item.get("criado_em", ""), reverse=True)
    return resumos


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


def orcamento_para_dict(orcamento, *, criado_em=None, atualizado_em=None):
    dados = orcamento.exportar_dict()
    dados["id"] = getattr(orcamento, "id", _novo_id())
    dados["estado_referencia"] = getattr(orcamento, "estado_referencia", "")
    agora = _agora_iso()
    dados["criado_em"] = criado_em or agora
    dados["atualizado_em"] = atualizado_em or agora
    return dados


def atualizar_orcamento_na_lista(orcamento, *, atualizar_data=True):
    dados = carregar_arquivo()
    payload = orcamento_para_dict(orcamento)
    for indice, orc in enumerate(dados.get("orcamentos", [])):
        if orc.get("id") == payload["id"]:
            payload["criado_em"] = orc.get("criado_em", payload["criado_em"])
            if not atualizar_data:
                payload["atualizado_em"] = orc.get("atualizado_em", payload["atualizado_em"])
            dados["orcamentos"][indice] = payload
            dados["orcamento_ativo_id"] = payload["id"]
            salvar_arquivo(dados)
            return dados
    raise ValueError("Orçamento não encontrado.")


def criar_orcamento(nome):
    dados = carregar_arquivo()
    orc = _orcamento_vazio_dict(nome.strip())
    dados.setdefault("orcamentos", []).append(orc)
    dados["orcamento_ativo_id"] = orc["id"]
    salvar_arquivo(dados)
    return orc["id"]


def adicionar_orcamento_importado(orcamento):
    dados = carregar_arquivo()
    payload = orcamento_para_dict(orcamento)
    payload["id"] = getattr(orcamento, "id", _novo_id())
    dados.setdefault("orcamentos", []).append(payload)
    dados["orcamento_ativo_id"] = payload["id"]
    salvar_arquivo(dados)
    return payload["id"]


def renomear_orcamento(orcamento_id, novo_nome):
    dados = carregar_arquivo()
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


def excluir_orcamento(orcamento_id):
    dados = carregar_arquivo()
    orcamentos = dados.get("orcamentos", [])
    restantes = [o for o in orcamentos if o.get("id") != orcamento_id]
    if len(restantes) == len(orcamentos):
        raise ValueError("Orçamento não encontrado.")
    dados["orcamentos"] = restantes
    if dados.get("orcamento_ativo_id") == orcamento_id:
        dados["orcamento_ativo_id"] = restantes[0]["id"] if restantes else None
    salvar_arquivo(dados)
    return dados.get("orcamento_ativo_id")
