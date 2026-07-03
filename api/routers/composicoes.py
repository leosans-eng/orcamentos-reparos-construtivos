"""Rotas do catálogo de composições próprias."""

from __future__ import annotations

import uuid
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.deps import get_current_user
from api.models import ComposicaoPropria, User
from api.schemas import (
    CatalogoComposicoesResponse,
    ComposicaoCreateRequest,
    ComposicaoUpdateRequest,
    EstadoPreviaRequest,
)
from api.seed import (
    ESTADO_PREVIA_CHAVE,
    incrementar_catalogo_composicoes_versao,
    obter_catalogo_composicoes_versao,
    obter_estado_previa,
)
from api.seed import _set_setting

router = APIRouter(prefix="/composicoes", tags=["composicoes"])


def _serializar_composicao(registro: ComposicaoPropria) -> dict:
    dados = deepcopy(registro.dados)
    dados["versao"] = registro.versao
    return dados


def _montar_catalogo(db: Session) -> CatalogoComposicoesResponse:
    registros = db.query(ComposicaoPropria).order_by(ComposicaoPropria.codigo).all()
    return CatalogoComposicoesResponse(
        versao=obter_catalogo_composicoes_versao(db),
        estado_previa_custos=obter_estado_previa(db),
        composicoes=[_serializar_composicao(r) for r in registros],
    )


@router.get("/catalogo", response_model=CatalogoComposicoesResponse)
def obter_catalogo(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _montar_catalogo(db)


@router.patch("/catalogo/estado-previa", response_model=CatalogoComposicoesResponse)
def atualizar_estado_previa(
    body: EstadoPreviaRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    estado = str(body.estado or "").strip()
    if not estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o estado.")
    _set_setting(db, ESTADO_PREVIA_CHAVE, {"estado": estado})
    return _montar_catalogo(db)


@router.get("/{composicao_id}")
def obter_composicao(
    composicao_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(ComposicaoPropria, composicao_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Composição não encontrada.")
    return _serializar_composicao(registro)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_composicao(
    body: ComposicaoCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    codigo = str(body.codigo).strip()
    nome = str(body.nome).strip()
    unidade = str(body.unidade).strip()
    if not codigo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o código da composição.")
    if not nome:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome da composição.")
    if not unidade:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe a unidade da composição.")
    if db.query(ComposicaoPropria).filter(ComposicaoPropria.codigo == codigo).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma composição com o código {codigo}.",
        )

    comp_id = uuid.uuid4()
    composicao = {
        "id": str(comp_id),
        "codigo": codigo,
        "nome": nome,
        "unidade": unidade,
        "componentes": body.componentes or [],
    }
    registro = ComposicaoPropria(
        id=comp_id,
        codigo=codigo,
        dados=composicao,
        versao=1,
    )
    db.add(registro)
    incrementar_catalogo_composicoes_versao(db)
    db.commit()
    db.refresh(registro)
    return _serializar_composicao(registro)


@router.put("/{composicao_id}")
def atualizar_composicao(
    composicao_id: uuid.UUID,
    body: ComposicaoUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(ComposicaoPropria, composicao_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Composição não encontrada.")

    if body.versao != registro.versao:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "conflito_versao",
                "mensagem": "Alguém alterou esta composição. Recarregue os dados e tente novamente.",
                "versao_atual": registro.versao,
            },
        )

    composicao = deepcopy(body.composicao)
    comp_id = str(composicao.get("id", "")).strip()
    if comp_id != str(composicao_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID da composição inconsistente.")

    codigo = str(composicao.get("codigo", "")).strip()
    if not codigo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o código da composição.")

    outra = (
        db.query(ComposicaoPropria)
        .filter(ComposicaoPropria.codigo == codigo, ComposicaoPropria.id != composicao_id)
        .first()
    )
    if outra:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe outra composição com o código {codigo}.",
        )

    composicao.pop("versao", None)
    registro.codigo = codigo
    registro.dados = composicao
    registro.versao += 1
    incrementar_catalogo_composicoes_versao(db)
    db.commit()
    db.refresh(registro)
    return _serializar_composicao(registro)


@router.delete("/{composicao_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_composicao(
    composicao_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    registro = db.get(ComposicaoPropria, composicao_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Composição não encontrada.")
    db.delete(registro)
    incrementar_catalogo_composicoes_versao(db)
    db.commit()
