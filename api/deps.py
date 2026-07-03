"""Dependências FastAPI (sessão DB, usuário autenticado)."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.auth import TokenInvalidoError, validar_token
from api.database import get_db
from api.models import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = validar_token(credentials.credentials)
    except TokenInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo.")
    return user


def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UUID | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = validar_token(credentials.credentials)
        uid = payload.get("uid")
        return UUID(str(uid)) if uid else None
    except (TokenInvalidoError, ValueError):
        return None
