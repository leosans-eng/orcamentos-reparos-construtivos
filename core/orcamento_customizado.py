"""
Modelo de dados para orçamentos customizados.

Estrutura hierárquica: grupos (ex.: Serviços preliminares) contendo itens SINAPI
ou composições próprias (placeholder para implementação futura).
"""

import uuid
from copy import deepcopy

TIPO_GRUPO = "grupo"
TIPO_SINAPI = "sinapi"
TIPO_COMPOSICAO_PROPRIA = "composicao_propria"

BDI_PADRAO = 30.62


def _novo_id():
    return str(uuid.uuid4())


def _criar_grupo(nome):
    return {
        "id": _novo_id(),
        "tipo": TIPO_GRUPO,
        "nome": nome.strip(),
        "itens": [],
    }


def _criar_item_sinapi(codigo, descricao, unidade, custo_unitario, quantidade, estado, tipo_sinapi=""):
    return {
        "id": _novo_id(),
        "tipo": TIPO_SINAPI,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "custo_unitario": float(custo_unitario),
        "quantidade": float(quantidade),
        "estado": str(estado).strip(),
        "tipo_sinapi": str(tipo_sinapi or "").strip().upper()[:1],
    }


def _criar_composicao_propria(
    composicao_catalogo_id,
    codigo,
    nome,
    unidade,
    quantidade=1.0,
    *,
    custo_unitario_referencia=None,
):
    item = {
        "id": _novo_id(),
        "tipo": TIPO_COMPOSICAO_PROPRIA,
        "composicao_catalogo_id": str(composicao_catalogo_id or "").strip(),
        "codigo": str(codigo).strip(),
        "nome": str(nome).strip(),
        "unidade": str(unidade).strip(),
        "quantidade": float(quantidade),
    }
    if custo_unitario_referencia is not None:
        item["custo_unitario_referencia"] = float(custo_unitario_referencia)
    return item


def aplicar_bdi(valor, bdi_percent):
    return float(valor) * (1 + float(bdi_percent) / 100)


def custo_unitario_com_bdi(custo_unitario, bdi_percent):
    return aplicar_bdi(custo_unitario, bdi_percent)


def subtotal_item_sem_bdi(item):
    if item["tipo"] == TIPO_SINAPI:
        return item["custo_unitario"] * item["quantidade"]
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        return 0.0
    return 0.0


def subtotal_item(item, bdi_percent: float = 0.0):
    base = subtotal_item_sem_bdi(item)
    if item["tipo"] == TIPO_SINAPI and bdi_percent:
        return aplicar_bdi(base, bdi_percent)
    return base


def subtotal_grupo(grupo, bdi_percent: float = 0.0):
    return sum(subtotal_item(i, bdi_percent) for i in grupo.get("itens", []))


def total_orcamento(grupos, bdi_percent: float = 0.0):
    return sum(subtotal_grupo(g, bdi_percent) for g in grupos)


def rotulo_item(item):
    if item["tipo"] == TIPO_SINAPI:
        return f"{item['codigo']} — {item['descricao']}"
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        codigo = item.get("codigo", "")
        nome = item.get("nome", "")
        if codigo:
            return f"{codigo} — {nome}"
        return f"[Composição própria] {nome}"
    return ""


class OrcamentoCustomizado:
    def __init__(self, nome="", bdi_percent=BDI_PADRAO, orcamento_id=None):
        self.id = orcamento_id or _novo_id()
        self.nome = nome.strip()
        self.bdi_percent = float(bdi_percent)
        self.estado_referencia = ""
        self.grupos = []

    def definir_nome(self, nome):
        self.nome = nome.strip()

    def definir_bdi(self, bdi_percent):
        self.bdi_percent = float(bdi_percent)

    def definir_estado_referencia(self, estado):
        self.estado_referencia = (estado or "").strip()

    def adicionar_grupo(self, nome):
        if not nome or not nome.strip():
            raise ValueError("Informe o nome do grupo.")
        grupo = _criar_grupo(nome)
        self.grupos.append(grupo)
        return grupo["id"]

    def obter_grupo(self, grupo_id):
        for grupo in self.grupos:
            if grupo["id"] == grupo_id:
                return grupo
        return None

    def obter_grupo_por_indice(self, indice):
        if 0 <= indice < len(self.grupos):
            return self.grupos[indice]
        return None

    def remover_grupo(self, grupo_id):
        self.grupos = [g for g in self.grupos if g["id"] != grupo_id]

    def renomear_grupo(self, grupo_id, nome):
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        if not nome or not nome.strip():
            raise ValueError("Informe o nome do grupo.")
        grupo["nome"] = nome.strip()

    def mover_grupo_para_posicao(self, grupo_id, posicao):
        """Move etapa para a posição informada (1 = primeira etapa)."""
        total = len(self.grupos)
        if posicao < 1 or posicao > total:
            raise ValueError(f"Informe uma posição entre 1 e {total}.")
        indice_atual = next(
            (i for i, grupo in enumerate(self.grupos) if grupo["id"] == grupo_id),
            None,
        )
        if indice_atual is None:
            raise ValueError("Grupo não encontrado.")
        novo_indice = posicao - 1
        if indice_atual == novo_indice:
            return False
        grupo = self.grupos.pop(indice_atual)
        self.grupos.insert(novo_indice, grupo)
        return True

    def mover_item(self, item_id, delta):
        grupo, item = self.obter_item(item_id)
        if item is None or grupo is None:
            raise ValueError("Item não encontrado.")
        itens = grupo["itens"]
        indice = next(i for i, candidato in enumerate(itens) if candidato["id"] == item_id)
        novo_indice = indice + delta
        if novo_indice < 0 or novo_indice >= len(itens):
            return False
        itens[indice], itens[novo_indice] = itens[novo_indice], itens[indice]
        return True

    def adicionar_item_sinapi(
        self, grupo_id, codigo, descricao, unidade, custo_unitario, quantidade, estado, tipo_sinapi=""
    ):
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item = _criar_item_sinapi(
            codigo, descricao, unidade, custo_unitario, quantidade, estado, tipo_sinapi
        )
        grupo["itens"].append(item)
        return item["id"]

    def adicionar_composicao_propria(
        self,
        grupo_id,
        composicao_catalogo_id,
        codigo,
        nome,
        unidade,
        quantidade=1.0,
        *,
        custo_unitario_referencia=None,
    ):
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        catalogo_id = str(composicao_catalogo_id or "").strip()
        if not catalogo_id and not str(codigo or "").strip() and not str(nome or "").strip():
            raise ValueError("Informe a composição do catálogo ou os dados do item.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item = _criar_composicao_propria(
            catalogo_id,
            codigo,
            nome,
            unidade,
            quantidade,
            custo_unitario_referencia=custo_unitario_referencia,
        )
        grupo["itens"].append(item)
        return item["id"]

    def obter_item(self, item_id):
        for grupo in self.grupos:
            for item in grupo["itens"]:
                if item["id"] == item_id:
                    return grupo, item
        return None, None

    def atualizar_quantidade(self, item_id, quantidade):
        _grupo, item = self.obter_item(item_id)
        if item is None:
            raise ValueError("Item não encontrado.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item["quantidade"] = float(quantidade)

    def substituir_item_sinapi(
        self, item_id, codigo, descricao, unidade, custo_unitario, estado, tipo_sinapi=""
    ):
        grupo, item = self.obter_item(item_id)
        if item is None or grupo is None:
            raise ValueError("Item não encontrado.")
        quantidade = item["quantidade"]
        novo_item = _criar_item_sinapi(
            codigo,
            descricao,
            unidade,
            custo_unitario,
            quantidade,
            estado,
            tipo_sinapi,
        )
        novo_item["id"] = item_id
        indice = next(i for i, candidato in enumerate(grupo["itens"]) if candidato["id"] == item_id)
        grupo["itens"][indice] = novo_item
        return item_id

    def substituir_por_composicao_propria(
        self, item_id, composicao_catalogo_id, codigo, nome, unidade
    ):
        grupo, item = self.obter_item(item_id)
        if item is None or grupo is None:
            raise ValueError("Item não encontrado.")
        if not composicao_catalogo_id:
            raise ValueError("Composição do catálogo não informada.")
        quantidade = item["quantidade"]
        novo_item = _criar_composicao_propria(
            composicao_catalogo_id, codigo, nome, unidade, quantidade
        )
        novo_item["id"] = item_id
        indice = next(i for i, candidato in enumerate(grupo["itens"]) if candidato["id"] == item_id)
        grupo["itens"][indice] = novo_item
        return item_id

    def remover_item(self, item_id):
        for grupo in self.grupos:
            antes = len(grupo["itens"])
            grupo["itens"] = [i for i in grupo["itens"] if i["id"] != item_id]
            if len(grupo["itens"]) < antes:
                return True
        return False

    def total(self, com_bdi=True):
        bdi = self.bdi_percent if com_bdi else 0
        return total_orcamento(self.grupos, bdi)

    def exportar_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "bdi_percent": self.bdi_percent,
            "estado_referencia": self.estado_referencia,
            "grupos": deepcopy(self.grupos),
        }

    @classmethod
    def importar_dict(cls, dados):
        orc = cls(
            dados.get("nome", ""),
            dados.get("bdi_percent", BDI_PADRAO),
            dados.get("id"),
        )
        orc.estado_referencia = dados.get("estado_referencia", "")
        orc.grupos = deepcopy(dados.get("grupos", []))
        return orc


def sincronizar_precos_sinapi_no_orcamento(orcamento, sinapi, estado):
    """Atualiza custos e tipo dos itens SINAPI conforme a base carregada."""
    estado_ref = str(estado or "").strip()
    if not estado_ref:
        return
    from core.sinapi_busca import obter_item_sinapi

    for grupo in orcamento.grupos:
        for item in grupo.get("itens", []):
            if item["tipo"] != TIPO_SINAPI:
                continue
            linha = obter_item_sinapi(sinapi, item["codigo"], estado_ref)
            if linha is None:
                continue
            try:
                item["custo_unitario"] = float(
                    linha.get("custo", item["custo_unitario"])
                )
            except (TypeError, ValueError):
                pass
            tipo = str(linha.get("tipo", "")).strip().upper()[:1]
            if tipo in ("I", "C"):
                item["tipo_sinapi"] = tipo
            item["estado"] = estado_ref


def rotulo_tipo_sinapi(item, sinapi=None) -> str:
    if item.get("tipo") != TIPO_SINAPI:
        return ""
    tipo = str(item.get("tipo_sinapi", "")).strip().upper()[:1]
    if tipo in ("I", "C"):
        return tipo
    if sinapi is not None:
        from core.sinapi_busca import obter_item_sinapi

        linha = obter_item_sinapi(sinapi, item.get("codigo", ""), item.get("estado", ""))
        if linha is not None:
            tipo = str(linha.get("tipo", "")).strip().upper()[:1]
            if tipo in ("I", "C"):
                return tipo
        from core.sinapi_base import SinapiBase

        if isinstance(sinapi, SinapiBase):
            tipo = sinapi.obter_tipo(item.get("codigo", ""))
            if tipo in ("I", "C"):
                return tipo
    return "—"


def item_indisponivel_na_base(item, sinapi, catalogo, estado) -> bool:
    """Mesmo critério do fundo amarelo na grade do orçamento."""
    from core.composicoes_proprias import custo_composicao_propria_item
    from core.sinapi_busca import item_sinapi_ausente

    if item["tipo"] == TIPO_SINAPI:
        return item_sinapi_ausente(sinapi, item["codigo"], estado)
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        _custo, tem_depreciado = custo_composicao_propria_item(
            item, catalogo, sinapi, estado
        )
        return tem_depreciado
    return False
