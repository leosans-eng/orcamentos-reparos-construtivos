"""Modelos do banco de dados da API ORC."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
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


class OrcamentoCustomizado(Base):
    """Orçamento customizado compartilhado entre usuários autenticados."""

    __tablename__ = "orcamentos_customizados"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dados: Mapped[dict] = mapped_column(JSON, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
