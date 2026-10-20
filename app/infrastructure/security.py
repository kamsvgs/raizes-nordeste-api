"""Hash de senha (bcrypt) e tokens JWT."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings
from app.domain.exceptions import NaoAutenticado


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False


def criar_token(usuario_id: int, perfil: str) -> tuple[str, int]:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    token = jwt.encode({"sub": str(usuario_id), "perfil": perfil, "exp": exp}, settings.SECRET_KEY,
                       algorithm=settings.JWT_ALGORITHM)
    return token, settings.ACCESS_TOKEN_MINUTES * 60


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise NaoAutenticado("Token expirado.")
    except jwt.PyJWTError:
        raise NaoAutenticado("Token inválido.")
