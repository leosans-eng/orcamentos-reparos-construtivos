"""Ponto de entrada da API ORC — Fases 1 e 3."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import Base, SessionLocal, engine
from api.routers import auth, composicoes, etapas, orcamentos
from api.seed import garantir_dados_iniciais

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
