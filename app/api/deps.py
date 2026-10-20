"""Dependências de injeção: sessão, usuário autenticado e gateway de pagamento."""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.domain.exceptions import NaoAutenticado
from app.domain.ports import PagamentoGateway
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import Usuario
from app.infrastructure.gateways.pagamento_mock import PagamentoGatewayMock
from app.infrastructure.security import decodificar_token

bearer = HTTPBearer(auto_error=False, description="Token JWT obtido em POST /auth/login")
_gateway = PagamentoGatewayMock()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_gateway() -> PagamentoGateway:
    return _gateway


def ip_origem(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> Usuario:
    if cred is None or cred.scheme.lower() != "bearer":
        raise NaoAutenticado("Token de acesso ausente.")
    dados = decodificar_token(cred.credentials)
    user = db.get(Usuario, int(dados["sub"]))
    if user is None or not user.ativo:
        raise NaoAutenticado("Usuário inválido ou inativo.")
    return user
