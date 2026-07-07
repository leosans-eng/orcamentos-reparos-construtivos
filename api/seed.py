"""Carga inicial do banco a partir dos JSON em dados_usuario/."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from api.auth import hash_password
from api.config import settings
from api.models import AppSetting, ComposicaoPropria, EtapaPredefinida, OrcamentoCustomizado, User
from api.schemas import BDI_PADRAO

logger = logging.getLogger(__name__)

ESTADO_PREVIA_CHAVE = "estado_previa_custos"
ESTADO_PREVIA_PADRAO = "SP"
CATALOGO_COMPOSICOES_VERSAO = "catalogo_composicoes_versao"
CATALOGO_ETAPAS_VERSAO = "catalogo_etapas_versao"


def _seed_dir() -> Path:
    base = Path(__file__).resolve().parent
    return (base / settings.seed_data_dir).resolve()


def _ler_json(nome_arquivo: str) -> dict | None:
    caminho = _seed_dir() / nome_arquivo
    if not caminho.is_file():
        logger.warning("Arquivo de seed não encontrado: %s", caminho)
        return None
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _get_setting(db: Session, chave: str, default: dict) -> dict:
    registro = db.get(AppSetting, chave)
    if registro is None:
        registro = AppSetting(chave=chave, valor=default)
        db.add(registro)
        db.commit()
        db.refresh(registro)
    return registro.valor


def _set_setting(db: Session, chave: str, valor: dict) -> None:
    registro = db.get(AppSetting, chave)
    if registro is None:
        db.add(AppSetting(chave=chave, valor=valor))
    else:
        registro.valor = valor
    db.commit()


def garantir_usuario_admin(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    usuario = User(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        permissions={"admin": True},
        is_active=True,
    )
    db.add(usuario)
    db.commit()
    logger.info("Usuário admin criado: %s", settings.admin_username)


def _parse_data_iso(valor) -> datetime | None:
    if not valor:
        return None
    try:
        texto = str(valor).replace("Z", "+00:00")
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _seed_orcamentos(db: Session) -> None:
    if db.query(OrcamentoCustomizado).count() > 0:
        return
    dados = _ler_json("orcamentos_customizados.json")
    if not dados or not dados.get("orcamentos"):
        logger.warning("Nenhum orçamento para importar no seed.")
        return

    agora = datetime.now(timezone.utc)
    for orc in dados["orcamentos"]:
        orc_id = uuid.UUID(str(orc["id"]))
        nome = str(orc.get("nome", "Sem nome")).strip() or "Sem nome"
        conteudo = {
            "bdi_percent": float(orc.get("bdi_percent", BDI_PADRAO)),
            "estado_referencia": str(orc.get("estado_referencia", "") or "").strip(),
            "grupos": orc.get("grupos", []),
        }
        criado = _parse_data_iso(orc.get("criado_em")) or agora
        atualizado = _parse_data_iso(orc.get("atualizado_em")) or criado
        registro = OrcamentoCustomizado(
            id=orc_id,
            nome=nome,
            dados=conteudo,
            versao=1,
            created_at=criado,
            updated_at=atualizado,
        )
        db.add(registro)
    db.commit()
    logger.info("Seed: %s orçamentos importados.", len(dados["orcamentos"]))


def garantir_dados_iniciais(db: Session) -> None:
    garantir_usuario_admin(db)

    if db.query(ComposicaoPropria).count() == 0:
        dados = _ler_json("composicoes_proprias.json")
        if dados and dados.get("composicoes"):
            for comp in dados["composicoes"]:
                comp_id = uuid.UUID(str(comp["id"]))
                codigo = str(comp.get("codigo", "")).strip()
                registro = ComposicaoPropria(
                    id=comp_id,
                    codigo=codigo,
                    dados=comp,
                    versao=1,
                )
                db.add(registro)
            estado = str(dados.get("estado_previa_custos", ESTADO_PREVIA_PADRAO)).strip()
            _set_setting(db, ESTADO_PREVIA_CHAVE, {"estado": estado or ESTADO_PREVIA_PADRAO})
            _set_setting(db, CATALOGO_COMPOSICOES_VERSAO, {"versao": int(dados.get("versao", 1))})
            db.commit()
            logger.info("Seed: %s composições importadas.", len(dados["composicoes"]))
        else:
            _set_setting(db, ESTADO_PREVIA_CHAVE, {"estado": ESTADO_PREVIA_PADRAO})
            _set_setting(db, CATALOGO_COMPOSICOES_VERSAO, {"versao": 1})
            logger.warning("Nenhuma composição para importar no seed.")

    if db.query(EtapaPredefinida).count() == 0:
        dados = _ler_json("etapas_predefinidas.json")
        if dados and dados.get("etapas"):
            for etapa in dados["etapas"]:
                etapa_id = uuid.UUID(str(etapa["id"]))
                registro = EtapaPredefinida(
                    id=etapa_id,
                    dados=etapa,
                    versao=1,
                )
                db.add(registro)
            _set_setting(db, CATALOGO_ETAPAS_VERSAO, {"versao": int(dados.get("versao", 1))})
            db.commit()
            logger.info("Seed: %s etapas importadas.", len(dados["etapas"]))
        else:
            _set_setting(db, CATALOGO_ETAPAS_VERSAO, {"versao": 1})
            logger.warning("Nenhuma etapa para importar no seed.")

    _seed_orcamentos(db)

    _get_setting(db, ESTADO_PREVIA_CHAVE, {"estado": ESTADO_PREVIA_PADRAO})
    _get_setting(db, CATALOGO_COMPOSICOES_VERSAO, {"versao": 1})
    _get_setting(db, CATALOGO_ETAPAS_VERSAO, {"versao": 1})


def obter_estado_previa(db: Session) -> str:
    valor = _get_setting(db, ESTADO_PREVIA_CHAVE, {"estado": ESTADO_PREVIA_PADRAO})
    estado = str(valor.get("estado", "")).strip()
    return estado or ESTADO_PREVIA_PADRAO


def obter_catalogo_composicoes_versao(db: Session) -> int:
    valor = _get_setting(db, CATALOGO_COMPOSICOES_VERSAO, {"versao": 1})
    return int(valor.get("versao", 1))


def obter_catalogo_etapas_versao(db: Session) -> int:
    valor = _get_setting(db, CATALOGO_ETAPAS_VERSAO, {"versao": 1})
    return int(valor.get("versao", 1))


def incrementar_catalogo_composicoes_versao(db: Session) -> None:
    atual = obter_catalogo_composicoes_versao(db)
    _set_setting(db, CATALOGO_COMPOSICOES_VERSAO, {"versao": atual + 1})


def incrementar_catalogo_etapas_versao(db: Session) -> None:
    atual = obter_catalogo_etapas_versao(db)
    _set_setting(db, CATALOGO_ETAPAS_VERSAO, {"versao": atual + 1})
