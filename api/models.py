"""Modelos do banco de dados — Fase 1."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ComposicaoPropria(Base):
    __tablename__ = "composicoes_proprias"
    __table_args__ = (UniqueConstraint("codigo", name="uq_composicoes_proprias_codigo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dados: Mapped[dict] = mapped_column(JSON, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class EtapaPredefinida(Base):
    __tablename__ = "etapas_predefinidas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    dados: Mapped[dict] = mapped_column(JSON, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    chave: Mapped[str] = mapped_column(String(128), primary_key=True)
    valor: Mapped[dict] = mapped_column(JSON, nullable=False)
