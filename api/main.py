"""Ponto de entrada da API ORC — Fases 1 e 3."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from api.database import Base, SessionLocal, engine
from api.routers import auth, composicoes, etapas, orcamentos
from api.seed import garantir_dados_iniciais

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MENSAGEM_BANCO_INDISPONIVEL = (
    "O banco de dados está indisponível. "
    "Verifique se o PostgreSQL está em execução e tente novamente."
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        garantir_dados_iniciais(db)
    finally:
        db.close()
    logger.info("API ORC iniciada.")
    yield


app = FastAPI(
    title="ORC API",
    description=(
        "API compartilhada do sistema ORC — Fase 1 (composições e etapas) "
        "e Fase 3 (orçamentos customizados)."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(composicoes.router, prefix="/api")
app.include_router(etapas.router, prefix="/api")
app.include_router(orcamentos.router, prefix="/api")


@app.exception_handler(OperationalError)
async def _tratar_erro_operacional(_request: Request, exc: OperationalError):
    logger.error("Falha de conexão com o banco: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": MENSAGEM_BANCO_INDISPONIVEL},
    )


@app.exception_handler(SQLAlchemyError)
async def _tratar_erro_sqlalchemy(_request: Request, exc: SQLAlchemyError):
    logger.error("Erro de banco de dados: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": MENSAGEM_BANCO_INDISPONIVEL},
    )


@app.get("/api/health")
def health():
    """Healthcheck: API + banco. Retorna 503 se o Postgres estiver fora."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Healthcheck: banco indisponível (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MENSAGEM_BANCO_INDISPONIVEL,
        ) from exc
    return {"status": "ok", "database": "ok"}
