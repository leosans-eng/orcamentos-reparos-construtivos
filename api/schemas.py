"""Schemas Pydantic da API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    permissions: dict[str, Any] = Field(default_factory=dict)


class UserPublic(BaseModel):
    id: UUID
    username: str
    permissions: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class ConflitoVersaoResponse(BaseModel):
    detail: str = "conflito_versao"
    mensagem: str
    versao_atual: int


class CatalogoComposicoesResponse(BaseModel):
    versao: int
    estado_previa_custos: str
    composicoes: list[dict[str, Any]]


class CatalogoEtapasResponse(BaseModel):
    versao: int
    etapas: list[dict[str, Any]]


class ComposicaoCreateRequest(BaseModel):
    codigo: str
    nome: str
    unidade: str
    componentes: list[dict[str, Any]] | None = None


class ComposicaoUpdateRequest(BaseModel):
    composicao: dict[str, Any]
    versao: int


class EtapaCreateRequest(BaseModel):
    nome: str


class EtapaUpdateRequest(BaseModel):
    etapa: dict[str, Any]
    versao: int


class EstadoPreviaRequest(BaseModel):
    estado: str
