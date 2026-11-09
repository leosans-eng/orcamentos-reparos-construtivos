"""Sincroniza o orçamento da Área Comum com anomalias e etapas pré-definidas."""

from __future__ import annotations

from copy import deepcopy

from core.area_comum_anomalias import (
    NOME_SERVICOS_PRELIMINARES,
    ORIGEM_SERVICOS_PRELIMINARES,
    TIPO_ITEM_CATALOGO_PROPRIA,
    itens_efetivos_reparo,
    normalizar_servicos_preliminares,
    obter_anomalia,
    quantidade_de_item,
    titulo_grupo_orcamento,
)
from core.area_comum_calculos import numero
from core.composicoes_proprias import obter_composicao_por_id
from core.etapas_predefinidas import aplicar_etapa_no_orcamento
from core.orcamento_customizado import TIPO_COMPOSICAO_PROPRIA, OrcamentoCustomizado
from core.sinapi_busca import escolher_estado_fallback_sinapi, obter_item_sinapi


def _catalogo_composicoes(catalogo_composicoes):
    if catalogo_composicoes is not None:
        return catalogo_composicoes
    try:
        from core.composicoes_proprias_storage import listar as listar_composicoes

        return listar_composicoes()
    except (ValueError, OSError, TypeError):
        return []


def _fator_percentual(texto) -> float:
    valor = numero(texto if texto not in (None, "") else "100", percentual=True)
    if valor < 0:
        return 0.0
    return valor / 100.0


def _titulo_grupo_anomalia(anomalia: dict, reparo: dict) -> str:
    return titulo_grupo_orcamento(anomalia, reparo)


def _custo_sinapi(sinapi, codigo: str, uf: str) -> tuple[float, str, str, str, str]:
    codigo = str(codigo or "").strip()
    uf = str(uf or "").strip()
    if not codigo or sinapi is None:
        return 0.0, "", "", uf, ""
    linha = obter_item_sinapi(sinapi, codigo, uf) if uf else None
    estado = uf
    if linha is None:
        alt = escolher_estado_fallback_sinapi(sinapi, codigo)
        if alt:
            linha = obter_item_sinapi(sinapi, codigo, alt)
            estado = alt
    if linha is None:
        return 0.0, "", "", estado, ""
    try:
        custo = float(linha.get("custo", 0) or 0)
    except (TypeError, ValueError):
        custo = 0.0
    tipo_ic = str(linha.get("tipo") or "").strip().upper()[:1]
    return (
        custo,
        str(linha.get("descricao") or "").strip(),
        str(linha.get("unidade") or "").strip(),
        estado,
        tipo_ic if tipo_ic in ("I", "C") else "",
    )


def _marcar_manual(grupo: dict | None) -> None:
    if grupo is None:
        return
    grupo["origem"] = "manual"


def _marcar_itens_origem_anomalia(grupo: dict | None) -> None:
    if grupo is None:
        return
    for item in grupo.get("itens") or []:
        item["origem_anomalia"] = True


def _chave_item_orcamento(item: dict) -> tuple:
    if item.get("tipo") == TIPO_COMPOSICAO_PROPRIA:
        return (
            "P",
            str(item.get("composicao_catalogo_id") or ""),
            str(item.get("codigo") or ""),
        )
    return ("S", str(item.get("codigo") or ""), "")


def _mesclar_grupo_anomalia(antigo: dict, novo: dict) -> dict:
    """Mantém itens extras, UF fixada e quantidades manuais ao reconstruir a etapa."""
    novo["id"] = antigo.get("id") or novo.get("id")
    itens_antigos = list(antigo.get("itens") or [])
    if itens_antigos and not any(i.get("origem_anomalia") for i in itens_antigos):
        for item in itens_antigos:
            item["origem_anomalia"] = True

    extras = [i for i in itens_antigos if not i.get("origem_anomalia")]
    template_novos = list(novo.get("itens") or [])
    for item in template_novos:
        item["origem_anomalia"] = True

    etapa_mudou = str(antigo.get("etapa_predefinida_id") or "") != str(
        novo.get("etapa_predefinida_id") or ""
    )
    if etapa_mudou:
        novo["itens"] = template_novos + extras
        return novo

    if not template_novos:
        for item in itens_antigos:
            if item.get("origem_anomalia") and not item.get("qtd_manual"):
                item["quantidade"] = 0.0
        novo["itens"] = itens_antigos
        return novo

    fila_por_chave: dict[tuple, list] = {}
    for item in itens_antigos:
        if not item.get("origem_anomalia"):
            continue
        fila_por_chave.setdefault(_chave_item_orcamento(item), []).append(item)

    mesclados = []
    for item in template_novos:
        fila = fila_por_chave.get(_chave_item_orcamento(item)) or []
        if not fila:
            continue
        velho = fila.pop(0)
        item["id"] = velho.get("id") or item.get("id")
        if velho.get("estado_fixado"):
            item["estado"] = velho.get("estado")
            item["estado_fixado"] = True
            try:
                item["custo_unitario"] = float(
                    velho.get("custo_unitario") or item.get("custo_unitario") or 0
                )
            except (TypeError, ValueError):
                pass
        if velho.get("discriminar_componentes"):
            item["discriminar_componentes"] = True
        if velho.get("qtd_manual"):
            item["quantidade"] = velho.get("quantidade")
            item["qtd_manual"] = True
        mesclados.append(item)

    mesclados_por_id = {item.get("id"): item for item in mesclados}
    ordenados = []
    vistos = set()
    for velho in itens_antigos:
        ident = velho.get("id")
        if velho.get("origem_anomalia"):
            atualizado = mesclados_por_id.get(ident)
            if atualizado is None:
                continue
            ordenados.append(atualizado)
        else:
            ordenados.append(velho)
        vistos.add(ident)
    for item in mesclados:
        if item.get("id") not in vistos:
            ordenados.append(item)
    novo["itens"] = ordenados
    return novo


def _grupo_vazio(nome: str) -> dict:
    tmp = OrcamentoCustomizado()
    grupo_id = tmp.adicionar_grupo(nome)
    return deepcopy(tmp.obter_grupo(grupo_id))


def _montar_grupo_etapa(
    *,
    etapa: dict,
    nome: str,
    quantidade: float,
    sinapi,
    uf: str,
    catalogo_composicoes,
) -> dict:
    qtd = float(quantidade or 0)
    if qtd <= 0:
        return _grupo_vazio(nome)
    tmp = OrcamentoCustomizado()
    grupo_id, _avisos = aplicar_etapa_no_orcamento(
        tmp,
        etapa or {"nome": nome, "itens": []},
        sinapi,
        uf,
        catalogo_composicoes,
        quantidade=qtd,
        nome_override=nome,
    )
    return deepcopy(tmp.obter_grupo(grupo_id) or _grupo_vazio(nome))


def _montar_grupo_itens_sinapi(
    *,
    nome: str,
    itens: list[dict],
    quantitativos: dict,
    percentual,
    sinapi,
    uf: str,
    catalogo_composicoes=None,
) -> dict:
    tmp = OrcamentoCustomizado()
    grupo_id = tmp.adicionar_grupo(nome)
    fator = _fator_percentual(percentual)
    catalogo_composicoes = _catalogo_composicoes(catalogo_composicoes)
    for item in itens or []:
        tipo = str(item.get("tipo") or "")
        qtd = quantidade_de_item(item, quantitativos) * fator
        if qtd <= 0:
            continue
        if tipo == TIPO_ITEM_CATALOGO_PROPRIA:
            catalogo_id = str(item.get("composicao_catalogo_id") or "").strip()
            composicao = (
                obter_composicao_por_id(catalogo_composicoes, catalogo_id)
                if catalogo_id
                else None
            )
            tmp.adicionar_composicao_propria(
                grupo_id,
                (composicao or {}).get("id", catalogo_id),
                (composicao or {}).get("codigo") or item.get("codigo") or "",
                (composicao or {}).get("nome")
                or item.get("nome")
                or item.get("codigo")
                or "Composição",
                (composicao or {}).get("unidade") or item.get("unidade") or "un",
                qtd,
            )
            continue
        codigo = str(item.get("codigo_sinapi") or item.get("codigo") or "").strip()
        if not codigo:
            continue
        custo, desc, unid, estado, tipo_ic = _custo_sinapi(sinapi, codigo, uf)
        unid = unid or str(item.get("unidade") or "")
        tmp.adicionar_item_sinapi(
            grupo_id,
            codigo,
            desc or codigo,
            unid,
            custo,
            qtd,
            estado or uf,
            tipo_ic,
        )
    return deepcopy(tmp.obter_grupo(grupo_id))


def _montar_grupo_servicos_preliminares(
    *,
    catalogo: dict,
    quantitativos: dict,
    sinapi,
    uf: str,
    catalogo_composicoes,
) -> dict | None:
    sp = normalizar_servicos_preliminares(
        (catalogo or {}).get("servicos_preliminares")
    )
    itens = list(sp.get("itens") or [])
    if not itens:
        return None
    nome = str(sp.get("nome") or "").strip() or NOME_SERVICOS_PRELIMINARES
    grupo = _montar_grupo_itens_sinapi(
        nome=nome,
        itens=itens,
        quantitativos=quantitativos,
        percentual="100",
        sinapi=sinapi,
        uf=uf,
        catalogo_composicoes=catalogo_composicoes,
    )
    grupo["origem"] = ORIGEM_SERVICOS_PRELIMINARES
    grupo["anomalia_id"] = ""
    grupo["etapa_predefinida_id"] = ""
    _marcar_itens_origem_anomalia(grupo)
    return grupo


def sincronizar_grupos_anomalias(
    orcamento: OrcamentoCustomizado,
    *,
    anomalias: list[dict],
    catalogo: dict,
    quantitativos: dict,
    etapas_por_id: dict,
    sinapi,
    uf: str,
    catalogo_composicoes=None,
    considerar_servicos_preliminares: bool = True,
) -> None:
    """Reconstrói grupos gerados por anomalias/SP e preserva etapas manuais."""
    catalogo_composicoes = _catalogo_composicoes(catalogo_composicoes)
    auto = []
    grupo_sp = None
    if considerar_servicos_preliminares:
        grupo_sp = _montar_grupo_servicos_preliminares(
            catalogo=catalogo,
            quantitativos=quantitativos,
            sinapi=sinapi,
            uf=uf,
            catalogo_composicoes=catalogo_composicoes,
        )
        if grupo_sp is not None:
            auto.append(grupo_sp)

    for anomalia in anomalias or []:
        nome = str(anomalia.get("nome") or "").strip()
        if not nome:
            continue
        cadastro = obter_anomalia(nome, catalogo) or {}
        reparos = list(cadastro.get("reparos") or [])
        rid = str(anomalia.get("reparo_id") or "")
        reparo = next((r for r in reparos if str(r.get("id")) == rid), None)
        if reparo is None and reparos:
            reparo = reparos[0]
        if reparo is None:
            continue
        titulo = _titulo_grupo_anomalia(anomalia, reparo)
        grupo = _montar_grupo_itens_sinapi(
            nome=titulo,
            itens=itens_efetivos_reparo(reparo, etapas_por_id),
            quantitativos=quantitativos,
            percentual=anomalia.get("percentual"),
            sinapi=sinapi,
            uf=uf,
            catalogo_composicoes=catalogo_composicoes,
        )
        grupo["origem"] = "anomalia"
        grupo["anomalia_id"] = str(anomalia.get("id") or "")
        grupo["etapa_predefinida_id"] = str(reparo.get("etapa_predefinida_id") or "")
        _marcar_itens_origem_anomalia(grupo)
        auto.append(grupo)

    origens_auto = {"anomalia", ORIGEM_SERVICOS_PRELIMINARES}
    manuais = [
        g for g in (orcamento.grupos or []) if g.get("origem") not in origens_auto
    ]
    por_anomalia = {
        str(g.get("anomalia_id") or ""): g
        for g in auto
        if g.get("origem") == "anomalia"
    }
    usados = set()
    resultado = []
    sp_inserido = False
    for antigo in orcamento.grupos or []:
        origem = antigo.get("origem")
        if origem == ORIGEM_SERVICOS_PRELIMINARES:
            if grupo_sp is None:
                continue
            resultado.append(_mesclar_grupo_anomalia(antigo, grupo_sp))
            sp_inserido = True
            continue
        if origem == "anomalia":
            aid = str(antigo.get("anomalia_id") or "")
            novo = por_anomalia.get(aid)
            if novo is None:
                continue
            resultado.append(_mesclar_grupo_anomalia(antigo, novo))
            usados.add(aid)
            continue
        resultado.append(antigo)

    if grupo_sp is not None and not sp_inserido:
        resultado.insert(0, grupo_sp)
    for grupo in auto:
        if grupo.get("origem") != "anomalia":
            continue
        aid = str(grupo.get("anomalia_id") or "")
        if aid not in usados:
            resultado.append(grupo)
    ids_resultado = {g.get("id") for g in resultado}
    for grupo in manuais:
        if grupo.get("id") not in ids_resultado:
            resultado.append(grupo)
    orcamento.grupos = resultado


def migrar_extras_para_grupos(
    orcamento: OrcamentoCustomizado,
    extras: list[dict],
    *,
    etapas_por_id: dict,
    sinapi,
    uf: str,
    catalogo_composicoes=None,
) -> None:
    """Converte extras_orcamento antigos em etapas manuais do OrcamentoCustomizado."""
    if not extras:
        return
    catalogo_composicoes = _catalogo_composicoes(catalogo_composicoes)
    grupo_itens_id = None
    for extra in extras:
        if not isinstance(extra, dict):
            continue
        if extra.get("tipo") == "etapa":
            nome = str(extra.get("nome") or "").strip() or "Etapa"
            qtd = numero(extra.get("quantidade") or "1")
            if qtd <= 0:
                qtd = 1.0
            etapa_id = str(extra.get("etapa_predefinida_id") or "")
            etapa = etapas_por_id.get(etapa_id)
            if etapa:
                grupo_id, _avisos = aplicar_etapa_no_orcamento(
                    orcamento,
                    etapa,
                    sinapi,
                    uf,
                    catalogo_composicoes,
                    quantidade=qtd,
                    nome_override=nome,
                )
            else:
                grupo_id = orcamento.adicionar_grupo(nome)
            _marcar_manual(orcamento.obter_grupo(grupo_id))
            continue
        if grupo_itens_id is None:
            grupo_itens_id = orcamento.adicionar_grupo("Itens específicos")
            _marcar_manual(orcamento.obter_grupo(grupo_itens_id))
        codigo = str(extra.get("codigo_sinapi") or "").strip()
        if not codigo:
            continue
        qtd = numero(extra.get("quantidade") or "1")
        if qtd <= 0:
            qtd = 1.0
        custo, desc, unid, estado, tipo_ic = _custo_sinapi(
            sinapi, codigo, extra.get("estado") or uf
        )
        try:
            custo_extra = float(extra.get("custo_unitario") or 0)
        except (TypeError, ValueError):
            custo_extra = 0.0
        if custo_extra:
            custo = custo_extra
        orcamento.adicionar_item_sinapi(
            grupo_itens_id,
            codigo,
            extra.get("descricao") or extra.get("nome") or desc or codigo,
            extra.get("unidade") or unid,
            custo,
            qtd,
            estado or uf,
            tipo_ic,
        )
