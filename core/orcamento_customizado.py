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


def _criar_item_sinapi(codigo, descricao, unidade, custo_unitario, quantidade, estado):
    return {
        "id": _novo_id(),
        "tipo": TIPO_SINAPI,
        "codigo": str(codigo).strip(),
        "descricao": str(descricao).strip(),
        "unidade": str(unidade).strip(),
        "custo_unitario": float(custo_unitario),
        "quantidade": float(quantidade),
        "estado": str(estado).strip(),
    }


def _criar_composicao_propria(nome, unidade, quantidade=1.0):
    """
    Placeholder para composições definidas pelo usuário.

    Futuro: ``componentes`` receberá insumos/composições SINAPI com coeficientes,
    ex. reparo de trincas com PU (unidade m) consumindo vários itens da base.
    """
    return {
        "id": _novo_id(),
        "tipo": TIPO_COMPOSICAO_PROPRIA,
        "nome": nome.strip(),
        "unidade": str(unidade).strip(),
        "quantidade": float(quantidade),
        "componentes": [],
    }


def aplicar_bdi(valor, bdi_percent):
    return float(valor) * (1 + float(bdi_percent) / 100)


def custo_unitario_com_bdi(custo_unitario, bdi_percent):
    return aplicar_bdi(custo_unitario, bdi_percent)


def subtotal_item_sem_bdi(item):
    if item["tipo"] == TIPO_SINAPI:
        return item["custo_unitario"] * item["quantidade"]
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        # Placeholder: custo será calculado a partir dos componentes no futuro.
        return 0.0
    return 0.0


def subtotal_item(item, bdi_percent=0):
    base = subtotal_item_sem_bdi(item)
    if item["tipo"] == TIPO_SINAPI and bdi_percent:
        return aplicar_bdi(base, bdi_percent)
    return base


def subtotal_grupo(grupo, bdi_percent=0):
    return sum(subtotal_item(i, bdi_percent) for i in grupo.get("itens", []))


def total_orcamento(grupos, bdi_percent=0):
    return sum(subtotal_grupo(g, bdi_percent) for g in grupos)


def rotulo_item(item):
    if item["tipo"] == TIPO_SINAPI:
        return f"{item['codigo']} — {item['descricao']}"
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        return f"[Composição própria] {item['nome']}"
    return ""


class OrcamentoCustomizado:
    def __init__(self, nome="", bdi_percent=BDI_PADRAO):
        self.nome = nome.strip()
        self.bdi_percent = float(bdi_percent)
        self.grupos = []

    def definir_nome(self, nome):
        self.nome = nome.strip()

    def definir_bdi(self, bdi_percent):
        self.bdi_percent = float(bdi_percent)

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

    def adicionar_item_sinapi(
        self, grupo_id, codigo, descricao, unidade, custo_unitario, quantidade, estado
    ):
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item = _criar_item_sinapi(
            codigo, descricao, unidade, custo_unitario, quantidade, estado
        )
        grupo["itens"].append(item)
        return item["id"]

    def adicionar_composicao_propria(self, grupo_id, nome, unidade, quantidade=1.0):
        """Registra composição própria (estrutura reservada para expansão futura)."""
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        if not nome or not nome.strip():
            raise ValueError("Informe o nome da composição.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item = _criar_composicao_propria(nome, unidade, quantidade)
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
            "nome": self.nome,
            "bdi_percent": self.bdi_percent,
            "grupos": deepcopy(self.grupos),
        }

    @classmethod
    def importar_dict(cls, dados):
        orc = cls(dados.get("nome", ""), dados.get("bdi_percent", BDI_PADRAO))
        orc.grupos = deepcopy(dados.get("grupos", []))
        return orc
