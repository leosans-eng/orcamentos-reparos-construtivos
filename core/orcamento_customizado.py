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


def _criar_item_sinapi(
    codigo,
    descricao,
    unidade,
    custo_unitario,
    quantidade,
    estado,
    tipo_sinapi="",
    *,
    estado_fixado=False,
):
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
        "estado_fixado": bool(estado_fixado),
    }


def estado_efetivo_item(item, estado_orcamento="") -> str:
    """UF usada para preço/disponibilidade do item (pode diferir do orçamento)."""
    if item.get("tipo") not in (TIPO_SINAPI, TIPO_COMPOSICAO_PROPRIA):
        return str(estado_orcamento or "").strip()
    if item.get("estado_fixado"):
        estado_item = str(item.get("estado", "")).strip()
        if estado_item:
            return estado_item
    return str(estado_orcamento or "").strip()


def item_usa_estado_alternativo(item, estado_orcamento="", catalogo=None) -> bool:
    """True quando o item usa UF diferente da do orçamento (própria ou via catálogo)."""
    estado_ref = str(estado_orcamento or "").strip()
    if item.get("tipo") == TIPO_SINAPI:
        if not item.get("estado_fixado"):
            return False
        estado_item = str(item.get("estado", "")).strip()
        return bool(estado_item) and estado_item != estado_ref
    if item.get("tipo") == TIPO_COMPOSICAO_PROPRIA:
        if item.get("estado_fixado"):
            estado_item = str(item.get("estado", "")).strip()
            if estado_item and estado_item != estado_ref:
                return True
        if catalogo is not None:
            from core.composicoes_proprias import (
                componente_usa_estado_alternativo,
                obter_composicao_por_id,
            )

            composicao = obter_composicao_por_id(
                catalogo, item.get("composicao_catalogo_id")
            )
            if composicao is None:
                return False
            estado_calc = estado_efetivo_item(item, estado_orcamento)
            return any(
                componente_usa_estado_alternativo(c, estado_calc)
                for c in composicao.get("componentes", [])
            )
    return False


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
        self,
        grupo_id,
        codigo,
        descricao,
        unidade,
        custo_unitario,
        quantidade,
        estado,
        tipo_sinapi="",
        *,
        estado_fixado=False,
    ):
        grupo = self.obter_grupo(grupo_id)
        if grupo is None:
            raise ValueError("Grupo não encontrado.")
        if quantidade <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        item = _criar_item_sinapi(
            codigo,
            descricao,
            unidade,
            custo_unitario,
            quantidade,
            estado,
            tipo_sinapi,
            estado_fixado=estado_fixado,
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
        self,
        item_id,
        codigo,
        descricao,
        unidade,
        custo_unitario,
        estado,
        tipo_sinapi="",
        *,
        estado_fixado=False,
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
            estado_fixado=estado_fixado,
        )
        novo_item["id"] = item_id
        indice = next(i for i, candidato in enumerate(grupo["itens"]) if candidato["id"] == item_id)
        grupo["itens"][indice] = novo_item
        return item_id

    def definir_estado_item_sinapi(self, item_id, estado, sinapi, *, fixar=None):
        """Altera a UF de preço de um item SINAPI sem mudar o estado do orçamento."""
        from core.sinapi_busca import obter_item_sinapi

        _grupo, item = self.obter_item(item_id)
        if item is None:
            raise ValueError("Item não encontrado.")
        if item.get("tipo") != TIPO_SINAPI:
            raise ValueError("Apenas itens SINAPI possuem estado próprio.")
        estado = str(estado or "").strip()
        if not estado:
            raise ValueError("Informe o estado.")
        linha = obter_item_sinapi(sinapi, item["codigo"], estado)
        if linha is None:
            raise ValueError(
                f"Código {item['codigo']} não encontrado para o estado {estado}."
            )
        try:
            item["custo_unitario"] = float(linha.get("custo", item["custo_unitario"]))
        except (TypeError, ValueError):
            pass
        tipo = str(linha.get("tipo", "")).strip().upper()[:1]
        if tipo in ("I", "C"):
            item["tipo_sinapi"] = tipo
        descricao = str(linha.get("descricao", "")).strip()
        if descricao:
            item["descricao"] = descricao
        unidade = str(linha.get("unidade", "")).strip()
        if unidade:
            item["unidade"] = unidade
        item["estado"] = estado
        if fixar is None:
            fixar = estado != str(self.estado_referencia or "").strip()
        item["estado_fixado"] = bool(fixar)

    def definir_estado_item_composicao(self, item_id, estado, *, fixar=None):
        """Fixa a UF de referência de uma composição própria neste orçamento."""
        _grupo, item = self.obter_item(item_id)
        if item is None:
            raise ValueError("Item não encontrado.")
        if item.get("tipo") != TIPO_COMPOSICAO_PROPRIA:
            raise ValueError("Item não é composição própria.")
        estado = str(estado or "").strip()
        if not estado:
            raise ValueError("Informe o estado.")
        item["estado"] = estado
        if fixar is None:
            fixar = estado != str(self.estado_referencia or "").strip()
        item["estado_fixado"] = bool(fixar)

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

    def _aplicar_linha(item, linha, estado_aplicado, *, fixado):
        try:
            item["custo_unitario"] = float(
                linha.get("custo", item["custo_unitario"])
            )
        except (TypeError, ValueError):
            pass
        tipo = str(linha.get("tipo", "")).strip().upper()[:1]
        if tipo in ("I", "C"):
            item["tipo_sinapi"] = tipo
        item["estado"] = estado_aplicado
        item["estado_fixado"] = bool(fixado)

    for grupo in orcamento.grupos:
        for item in grupo.get("itens", []):
            if item["tipo"] != TIPO_SINAPI:
                continue
            if item.get("estado_fixado"):
                estado_item = str(item.get("estado", "")).strip()
                if not estado_item:
                    continue
                linha = obter_item_sinapi(sinapi, item["codigo"], estado_item)
                if linha is None:
                    continue
                _aplicar_linha(item, linha, estado_item, fixado=True)
                continue

            linha = obter_item_sinapi(sinapi, item["codigo"], estado_ref)
            if linha is None:
                estado_alt = str(item.get("estado", "")).strip()
                if (
                    estado_alt
                    and estado_alt != estado_ref
                    and obter_item_sinapi(sinapi, item["codigo"], estado_alt) is not None
                ):
                    item["estado_fixado"] = True
                continue
            _aplicar_linha(item, linha, estado_ref, fixado=False)


def rotulo_tipo_sinapi(item, sinapi=None) -> str:
    if item.get("tipo") != TIPO_SINAPI:
        return ""
    tipo = str(item.get("tipo_sinapi", "")).strip().upper()[:1]
    if tipo in ("I", "C"):
        return tipo
    if sinapi is not None:
        from core.sinapi_busca import obter_item_sinapi

        linha = obter_item_sinapi(
            sinapi,
            item.get("codigo", ""),
            estado_efetivo_item(item, item.get("estado", "")),
        )
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
        estado_item = estado_efetivo_item(item, estado)
        return item_sinapi_ausente(sinapi, item["codigo"], estado_item)
    if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
        _custo, tem_depreciado = custo_composicao_propria_item(
            item, catalogo, sinapi, estado
        )
        return tem_depreciado
    return False
