"""Casos de uso de contas: cadastro, login, usuários internos e direitos do titular (UC01, RF19)."""
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.comum import cliente_do_usuario, exigir_perfil
from app.domain.enums import PerfilUsuario as P
from app.domain.exceptions import Conflito, CredenciaisInvalidas, NaoEncontrado
from app.infrastructure import auditoria
from app.infrastructure.db.models import Cliente, Unidade, Usuario, agora
from app.infrastructure.security import criar_token, hash_senha, verificar_senha


def _email_existe(db: Session, email: str) -> bool:
    return db.scalar(select(Usuario.id).where(Usuario.email == email.lower())) is not None


def registrar_cliente(db: Session, nome: str, email: str, senha: str, telefone: str | None,
                      data_nascimento: date | None, ip: str | None) -> Usuario:
    if _email_existe(db, email):
        raise Conflito("Já existe um cadastro com este e-mail.", "EMAIL_JA_CADASTRADO")
    u = Usuario(nome=nome, email=email.lower(), senha_hash=hash_senha(senha), perfil=P.CLIENTE)
    db.add(u)
    db.flush()
    db.add(Cliente(usuario_id=u.id, telefone=telefone, data_nascimento=data_nascimento))
    auditoria.registrar(db, u.id, "CLIENTE_CADASTRADO", "usuario", u.id, {}, ip)
    db.commit()
    return u


def autenticar(db: Session, email: str, senha: str, ip: str | None):
    u = db.scalar(select(Usuario).where(Usuario.email == email.lower()))
    if u is None or not u.ativo or not verificar_senha(senha, u.senha_hash):
        auditoria.registrar(db, u.id if u else None, "LOGIN_FALHOU", "usuario", u.id if u else None, {}, ip)
        db.commit()
        raise CredenciaisInvalidas("E-mail ou senha incorretos.")
    token, expira = criar_token(u.id, u.perfil.value)
    return u, token, expira


def criar_usuario_interno(db: Session, admin: Usuario, nome: str, email: str, senha: str, perfil: P,
                          unidade_id: int, ip: str | None) -> Usuario:
    exigir_perfil(admin, P.ADMIN)
    if db.get(Unidade, unidade_id) is None:
        raise NaoEncontrado("Unidade não encontrada.", "UNIDADE_NAO_ENCONTRADA")
    if _email_existe(db, email):
        raise Conflito("Já existe um cadastro com este e-mail.", "EMAIL_JA_CADASTRADO")
    u = Usuario(nome=nome, email=email.lower(), senha_hash=hash_senha(senha), perfil=perfil, unidade_id=unidade_id)
    db.add(u)
    db.flush()
    auditoria.registrar(db, admin.id, "USUARIO_CRIADO", "usuario", u.id, {"perfil": perfil.value}, ip)
    db.commit()
    return u


def dados_do_cliente(db: Session, user: Usuario) -> Cliente:
    exigir_perfil(user, P.CLIENTE)
    c = cliente_do_usuario(db, user)
    if c is None:
        raise NaoEncontrado("Cliente não encontrado.", "CLIENTE_NAO_ENCONTRADO")
    return c


def consultar_dados_pessoais(db: Session, user: Usuario, ip: str | None) -> Cliente:
    """Direito de acesso (LGPD art. 18): a consulta a dados pessoais também é auditada."""
    c = dados_do_cliente(db, user)
    auditoria.registrar(db, user.id, "DADOS_PESSOAIS_CONSULTADOS", "cliente", c.id, {}, ip)
    db.commit()
    return c


def anonimizar_cliente(db: Session, user: Usuario, ip: str | None) -> None:
    """Direito de eliminação (LGPD art. 18): remove dados identificáveis, preserva o histórico transacional."""
    c = dados_do_cliente(db, user)
    user.nome = "Cliente anonimizado"
    user.email = f"anonimizado-{user.id}@anonimo.invalid"
    user.senha_hash = hash_senha(secrets.token_urlsafe(24))
    user.ativo = False
    c.telefone = None
    c.data_nascimento = None
    c.anonimizado_em = agora()
    auditoria.registrar(db, user.id, "CLIENTE_ANONIMIZADO", "cliente", c.id, {}, ip)
    db.commit()
