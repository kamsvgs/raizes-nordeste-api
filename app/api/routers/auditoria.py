from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db
from app.application.comum import exigir_perfil
from app.domain.enums import PerfilUsuario
from app.infrastructure.db.models import AuditoriaLog, Usuario

router = APIRouter(tags=["Auditoria e sistema"])


@router.get("/auditoria", response_model=s.Page[s.AuditoriaOut], summary="Consultar trilha de auditoria (ADMIN)")
def auditoria(entidade: str | None = None, acao: str | None = None, entidade_id: int | None = Query(None, alias="entidadeId"),
              page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
              user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_perfil(user, PerfilUsuario.ADMIN)
    q = select(AuditoriaLog)
    if entidade:
        q = q.where(AuditoriaLog.entidade == entidade)
    if acao:
        q = q.where(AuditoriaLog.acao == acao)
    if entidade_id:
        q = q.where(AuditoriaLog.entidade_id == entidade_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    itens = db.scalars(q.order_by(AuditoriaLog.id.desc()).offset((page - 1) * limit).limit(limit)).all()
    return s.Page(items=itens, page=page, limit=limit, total=int(total or 0))


@router.get("/health", summary="Verificação de saúde")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}
