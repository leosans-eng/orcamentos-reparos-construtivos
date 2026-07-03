"""Rotas das etapas pré-definidas."""

from __future__ import annotations

import uuid
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import EtapaPredefinida, User
from api.schemas import CatalogoEtapasResponse, EtapaCreateRequest, EtapaUpdateRequest
from api.seed import incrementar_catalogo_etapas_versao, obter_catalogo_etapas_versao

router = APIRouter(prefix="/etapas", tags=["etapas"])


def _serializar_etapa(registro: EtapaPredefinida) -> dict:
    dados = deepcopy(registro.dados)
    dados["versao"] = registro.versao
    return dados


def _montar_catalogo(db: Session) -> CatalogoEtapasResponse:
    registros = db.query(EtapaPredefinida).all()
    registros.sort(key=lambda r: str(r.dados.get("nome", "")).casefold())
    return CatalogoEtapasResponse(
        versao=obter_catalogo_etapas_versao(db),
        etapas=[_serializar_etapa(r) for r in registros],
    )


@router.get("/catalogo", response_model=CatalogoEtapasResponse)
def obter_catalogo(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _montar_catalogo(db)


@router.get("/{etapa_id}")
def obter_etapa(
    etapa_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(EtapaPredefinida, etapa_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etapa não encontrada.")
    return _serializar_etapa(registro)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_etapa(
    body: EtapaCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    nome = str(body.nome).strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome da etapa.")

    etapa_id = uuid.uuid4()
    etapa = {
        "id": str(etapa_id),
        "nome": nome,
        "itens": [],
    }
    registro = EtapaPredefinida(
        id=etapa_id,
        dados=etapa,
        versao=1,
    )
    db.add(registro)
    incrementar_catalogo_etapas_versao(db)
    db.commit()
    db.refresh(registro)
    return _serializar_etapa(registro)


@router.put("/{etapa_id}")
def atualizar_etapa(
    etapa_id: uuid.UUID,
    body: EtapaUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(EtapaPredefinida, etapa_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etapa não encontrada.")

    if body.versao != registro.versao:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "conflito_versao",
                "mensagem": "Alguém alterou esta etapa. Recarregue os dados e tente novamente.",
                "versao_atual": registro.versao,
            },
        )

    etapa = deepcopy(body.etapa)
    etapa_id_str = str(etapa.get("id", "")).strip()
    if etapa_id_str != str(etapa_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID da etapa inconsistente.")

    nome = str(etapa.get("nome", "")).strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome da etapa.")

    etapa.pop("versao", None)
    registro.dados = etapa
    registro.versao += 1
    incrementar_catalogo_etapas_versao(db)
    db.commit()
    db.refresh(registro)
    return _serializar_etapa(registro)


@router.delete("/{etapa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_etapa(
    etapa_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(EtapaPredefinida, etapa_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etapa não encontrada.")
    db.delete(registro)
    incrementar_catalogo_etapas_versao(db)
    db.commit()
