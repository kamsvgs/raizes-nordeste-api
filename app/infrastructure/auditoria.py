"""Registro de auditoria – gravado na mesma transação da ação (decisão D7)."""
from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditoriaLog


def registrar(db: Session, usuario_id: int | None, acao: str, entidade: str, entidade_id: int | None = None,
              detalhes: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditoriaLog(usuario_id=usuario_id, acao=acao, entidade=entidade, entidade_id=entidade_id,
                        detalhes=detalhes or {}, ip_origem=ip))
