"""Rotas de autenticação."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import create_access_token, hash_password, verify_password
from api.database import get_db
from api.deps import get_current_user
from api.models import User
from api.schemas import LoginRequest, TokenResponse, UserCreateRequest, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")
    token = create_access_token(user.username, user.id)
    return TokenResponse(access_token=token, username=user.username)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    if not admin.permissions.get("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas administradores.")
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário já existe.")
    user = User(
        username=username,
        password_hash=hash_password(body.password),
        permissions=body.permissions,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
