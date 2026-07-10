"""Rotas dos orçamentos customizados compartilhados."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import OrcamentoCustomizado, User
from api.schemas import (
    BDI_PADRAO,
    OrcamentoCreateRequest,
    OrcamentoDuplicarRequest,
    OrcamentoListResponse,
    OrcamentoRenomearRequest,
    OrcamentoResumo,
    OrcamentoUpdateRequest,
)

router = APIRouter(prefix="/orcamentos", tags=["orcamentos"])


def _contar_grupos_itens(dados: dict) -> tuple[int, int]:
    grupos = dados.get("grupos", [])
    if not isinstance(grupos, list):
        return 0, 0
    total_itens = 0
    for grupo in grupos:
        if isinstance(grupo, dict):
            itens = grupo.get("itens", [])
            if isinstance(itens, list):
                total_itens += len(itens)
    return len(grupos), total_itens


def _dados_vazios() -> dict:
    return {
        "bdi_percent": BDI_PADRAO,
        "estado_referencia": "",
        "grupos": [],
    }


def _extrair_conteudo_orcamento(body: dict) -> dict:
    return {
        "bdi_percent": float(body.get("bdi_percent", BDI_PADRAO)),
        "estado_referencia": str(body.get("estado_referencia", "") or "").strip(),
        "grupos": deepcopy(body.get("grupos", [])),
    }


def _validar_grupos(grupos) -> None:
    if not isinstance(grupos, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O campo grupos deve ser uma lista.",
        )


def _serializar_orcamento(registro: OrcamentoCustomizado) -> dict:
    dados = deepcopy(registro.dados or {})
    return {
        "id": str(registro.id),
        "nome": registro.nome,
        "bdi_percent": dados.get("bdi_percent", BDI_PADRAO),
        "estado_referencia": dados.get("estado_referencia", ""),
        "grupos": dados.get("grupos", []),
        "versao": registro.versao,
        "criado_em": registro.created_at,
        "atualizado_em": registro.updated_at,
    }


def _serializar_resumo(registro: OrcamentoCustomizado) -> OrcamentoResumo:
    grupos, itens = _contar_grupos_itens(registro.dados or {})
    return OrcamentoResumo(
        id=registro.id,
        nome=registro.nome,
        versao=registro.versao,
        criado_em=registro.created_at,
        atualizado_em=registro.updated_at,
        grupos=grupos,
        itens=itens,
    )


def _verificar_conflito_versao(registro: OrcamentoCustomizado, versao_cliente: int) -> None:
    if versao_cliente != registro.versao:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "conflito_versao",
                "mensagem": "Alguém alterou este orçamento. Recarregue os dados e tente novamente.",
                "versao_atual": registro.versao,
            },
        )


def _regenerar_ids_orcamento(dados: dict) -> dict:
    """Gera novos UUIDs para orçamento duplicado (grupos e itens)."""
    copia = deepcopy(dados)
    grupos = copia.get("grupos", [])
    if not isinstance(grupos, list):
        copia["grupos"] = []
        return copia

    for grupo in grupos:
        if not isinstance(grupo, dict):
            continue
        grupo["id"] = str(uuid.uuid4())
        itens = grupo.get("itens", [])
        if not isinstance(itens, list):
            grupo["itens"] = []
            continue
        for item in itens:
            if isinstance(item, dict):
                item["id"] = str(uuid.uuid4())
    return copia


@router.get("", response_model=OrcamentoListResponse)
def listar_orcamentos(
    q: str | None = Query(default=None, description="Filtrar por nome (contém)"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    consulta = db.query(OrcamentoCustomizado)
    filtro = str(q or "").strip()
    if filtro:
        consulta = consulta.filter(OrcamentoCustomizado.nome.ilike(f"%{filtro}%"))
    registros = consulta.order_by(OrcamentoCustomizado.created_at.desc()).all()
    return OrcamentoListResponse(orcamentos=[_serializar_resumo(r) for r in registros])


@router.get("/{orcamento_id}")
def obter_orcamento(
    orcamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(OrcamentoCustomizado, orcamento_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    return _serializar_orcamento(registro)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_orcamento(
    body: OrcamentoCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    nome = str(body.nome).strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome do orçamento.")

    orcamento_id = uuid.uuid4()
    registro = OrcamentoCustomizado(
        id=orcamento_id,
        nome=nome,
        dados=_dados_vazios(),
        versao=1,
        created_by_id=user.id,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return _serializar_orcamento(registro)


@router.put("/{orcamento_id}")
def atualizar_orcamento(
    orcamento_id: uuid.UUID,
    body: OrcamentoUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(OrcamentoCustomizado, orcamento_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    _verificar_conflito_versao(registro, body.versao)

    payload = deepcopy(body.orcamento)
    payload_id = str(payload.get("id", "")).strip()
    if payload_id and payload_id != str(orcamento_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID do orçamento inconsistente.")

    nome = str(payload.get("nome", registro.nome)).strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome do orçamento.")

    conteudo = _extrair_conteudo_orcamento(payload)
    _validar_grupos(conteudo["grupos"])

    registro.nome = nome
    registro.dados = conteudo
    registro.versao += 1
    registro.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(registro)
    return _serializar_orcamento(registro)


@router.patch("/{orcamento_id}/nome")
def renomear_orcamento(
    orcamento_id: uuid.UUID,
    body: OrcamentoRenomearRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(OrcamentoCustomizado, orcamento_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    _verificar_conflito_versao(registro, body.versao)

    nome = str(body.nome).strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome do orçamento.")

    registro.nome = nome
    registro.versao += 1
    registro.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(registro)
    return _serializar_orcamento(registro)


@router.post("/{orcamento_id}/duplicar", status_code=status.HTTP_201_CREATED)
def duplicar_orcamento(
    orcamento_id: uuid.UUID,
    body: OrcamentoDuplicarRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    origem = db.get(OrcamentoCustomizado, orcamento_id)
    if origem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    nome = str(body.nome or f"Cópia de {origem.nome}").strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome do orçamento.")

    novo_id = uuid.uuid4()
    dados_copia = _regenerar_ids_orcamento(origem.dados or _dados_vazios())
    registro = OrcamentoCustomizado(
        id=novo_id,
        nome=nome,
        dados=dados_copia,
        versao=1,
        created_by_id=user.id,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return _serializar_orcamento(registro)


@router.delete("/{orcamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_orcamento(
    orcamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(OrcamentoCustomizado, orcamento_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    db.delete(registro)
    db.commit()
