"""Rotas de autenticação."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import create_access_token, hash_password, verify_password
from api.database import get_db
from api.deps import get_current_user
from api.models import User
from api.schemas import (
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserActiveRequest,
    UserCreateRequest,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _exigir_admin(user: User) -> None:
    if not user.permissions.get("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores.",
        )


def _obter_usuario(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )
    return user


def _contar_admins_ativos(db: Session) -> int:
    admins = db.query(User).filter(User.is_active.is_(True)).all()
    return sum(1 for u in admins if u.permissions.get("admin"))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    username = body.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o usuário.",
        )
    if not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe a senha.",
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inexistente.",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha incorreta.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Contate o administrador.",
        )
    token = create_access_token(user.username, user.id)
    return TokenResponse(access_token=token, username=user.username)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def trocar_senha(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.senha_atual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe a senha atual.",
        )
    if not body.senha_nova:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe a nova senha.",
        )
    if not verify_password(body.senha_atual, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta.",
        )
    if body.senha_atual == body.senha_nova:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da atual.",
        )
    user.password_hash = hash_password(body.senha_nova)
    db.add(user)
    db.commit()
    return {"detail": "Senha alterada com sucesso."}


@router.get("/users", response_model=list[UserPublic])
def listar_usuarios(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    _exigir_admin(admin)
    return db.query(User).order_by(User.username).all()


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    _exigir_admin(admin)
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


@router.post("/users/{user_id}/reset-password")
def redefinir_senha_usuario(
    user_id: UUID,
    body: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    """Admin define uma nova senha quando o usuário esqueceu a atual."""
    _exigir_admin(admin)
    if not body.senha_nova:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe a nova senha.",
        )
    user = _obter_usuario(db, user_id)
    user.password_hash = hash_password(body.senha_nova)
    db.add(user)
    db.commit()
    return {"detail": f"Senha de '{user.username}' redefinida com sucesso."}


@router.patch("/users/{user_id}/active", response_model=UserPublic)
def definir_usuario_ativo(
    user_id: UUID,
    body: UserActiveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    """Ativa ou desativa o acesso do usuário (bloqueio sem excluir)."""
    _exigir_admin(admin)
    user = _obter_usuario(db, user_id)
    if user.id == admin.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode desativar a própria conta.",
        )
    if (
        user.permissions.get("admin")
        and user.is_active
        and not body.is_active
        and _contar_admins_ativos(db) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar o único administrador ativo.",
        )
    user.is_active = body.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    _exigir_admin(admin)
    user = _obter_usuario(db, user_id)
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir a própria conta.",
        )
    if user.permissions.get("admin") and user.is_active and _contar_admins_ativos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir o único administrador ativo.",
        )
    db.delete(user)
    db.commit()
