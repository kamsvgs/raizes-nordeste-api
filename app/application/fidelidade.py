"""Casos de uso de consentimento e fidelidade (UC10)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.contas import dados_do_cliente
from app.domain.enums import FinalidadeDados
from app.infrastructure import auditoria
from app.infrastructure.db.models import Consentimento, MovimentoFidelidade, Usuario
from app.infrastructure.db.repositorios import FidelidadeRepo


def registrar_consentimento(db: Session, user: Usuario, finalidade: FinalidadeDados, concedido: bool,
                            versao: str, ip: str | None) -> Consentimento:
    c = dados_do_cliente(db, user)
    reg = Consentimento(cliente_id=c.id, finalidade=finalidade, concedido=concedido, versao_termo=versao)
    db.add(reg)
    db.flush()
    auditoria.registrar(db, user.id, "CONSENTIMENTO_REGISTRADO", "consentimento", reg.id,
                        {"finalidade": finalidade.value, "concedido": concedido, "versaoTermo": versao}, ip)
    db.commit()
    return reg


def consentimentos(db: Session, user: Usuario):
    c = dados_do_cliente(db, user)
    historico = db.scalars(select(Consentimento).where(Consentimento.cliente_id == c.id)
                           .order_by(Consentimento.id.desc())).all()
    vigentes = {}
    for h in historico:  # mais recente primeiro
        vigentes.setdefault(h.finalidade, h)
    return list(vigentes.values()), historico


def saldo(db: Session, user: Usuario) -> int:
    return FidelidadeRepo(db).saldo(dados_do_cliente(db, user).id)


def historico(db: Session, user: Usuario, page: int, limit: int):
    c = dados_do_cliente(db, user)
    base = select(MovimentoFidelidade).where(MovimentoFidelidade.cliente_id == c.id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    itens = db.scalars(base.order_by(MovimentoFidelidade.id.desc()).offset((page - 1) * limit).limit(limit)).all()
    return itens, int(total or 0)
