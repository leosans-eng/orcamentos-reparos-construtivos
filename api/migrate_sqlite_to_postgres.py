"""
Copia dados de um SQLite de desenvolvimento para o PostgreSQL configurado em api/.env.

Uso (na raiz do projeto, com o venv ativo e o Postgres no ar):

  .venv\\Scripts\\python.exe -m api.migrate_sqlite_to_postgres
  .venv\\Scripts\\python.exe -m api.migrate_sqlite_to_postgres --sqlite api/orc_dev.db
  .venv\\Scripts\\python.exe api/migrate_sqlite_to_postgres.py
  .venv\\Scripts\\python.exe api/migrate_sqlite_to_postgres.py --sqlite api/orc_dev.db

Requisitos:
  - DATABASE_URL em api/.env apontando para PostgreSQL
  - Arquivo SQLite existente (padrão: api/orc_dev.db)
  - Postgres vazio nas tabelas do ORC (ou use --force para apagar e recriar via create_all)

Não sobrescreve usuários/dados já existentes no Postgres, a menos que --force seja passado.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings
from api.database import Base
from api.models import (
    AppSetting,
    ComposicaoPropria,
    EtapaPredefinida,
    OrcamentoCustomizado,
    User,
)

DEFAULT_SQLITE = ROOT / "api" / "orc_dev.db"

TABELAS = (User, ComposicaoPropria, EtapaPredefinida, AppSetting, OrcamentoCustomizado)


def _sqlite_url(caminho: Path) -> str:
    return f"sqlite:///{caminho.resolve().as_posix()}"


def _contar(db: Session, modelo) -> int:
    return db.query(modelo).count()


def migrar(sqlite_path: Path, *, force: bool) -> None:
    if not settings.database_url.startswith("postgresql"):
        raise SystemExit(
            "DATABASE_URL em api/.env deve apontar para PostgreSQL.\n"
            f"Atual: {settings.database_url!r}"
        )
    if not sqlite_path.is_file():
        raise SystemExit(f"Arquivo SQLite não encontrado: {sqlite_path}")

    src_engine = create_engine(
        _sqlite_url(sqlite_path),
        connect_args={"check_same_thread": False},
    )
    dst_engine = create_engine(settings.database_url, pool_pre_ping=True)
    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)

    Base.metadata.create_all(bind=dst_engine)

    with DstSession() as dst:
        existentes = sum(_contar(dst, m) for m in TABELAS)
        if existentes and not force:
            raise SystemExit(
                f"PostgreSQL já tem {existentes} registro(s) nas tabelas do ORC.\n"
                "Use --force para limpar as tabelas e migrar de novo "
                "(apaga dados atuais do Postgres)."
            )
        if force and existentes:
            print("Limpando tabelas no PostgreSQL (--force)...")
            for modelo in reversed(TABELAS):
                dst.execute(text(f'TRUNCATE TABLE "{modelo.__tablename__}" CASCADE'))
            dst.commit()

    copiados = {m.__tablename__: 0 for m in TABELAS}
    with SrcSession() as src, DstSession() as dst:
        for modelo in TABELAS:
            linhas = src.scalars(select(modelo)).all()
            for linha in linhas:
                dst.merge(linha)
            copiados[modelo.__tablename__] = len(linhas)
        dst.commit()

    print("Migração concluída.")
    for tabela, n in copiados.items():
        print(f"  {tabela}: {n}")
    print(f"Destino: {settings.database_url.split('@')[-1]}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migra SQLite -> PostgreSQL (API ORC)")
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=DEFAULT_SQLITE,
        help=f"Caminho do .db (padrão: {DEFAULT_SQLITE})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apaga dados das tabelas ORC no Postgres antes de copiar",
    )
    args = parser.parse_args(argv)
    migrar(args.sqlite, force=args.force)


if __name__ == "__main__":
    main()
