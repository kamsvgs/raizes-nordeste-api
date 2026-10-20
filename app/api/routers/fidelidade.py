from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db, ip_origem
from app.application import fidelidade
from app.infrastructure.db.models import Usuario

router = APIRouter(prefix="/fidelidade", tags=["Fidelidade e consentimento"])


def _cons(c) -> s.ConsentimentoOut:
    return s.ConsentimentoOut(finalidade=c.finalidade, concedido=c.concedido, versao_termo=c.versao_termo,
                              registrado_em=c.registrado_em)


@router.post("/consentimentos", response_model=s.ConsentimentoOut, status_code=201,
             summary="Conceder ou revogar consentimento")
def registrar(body: s.ConsentimentoIn, request: Request, user: Usuario = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return _cons(fidelidade.registrar_consentimento(db, user, body.finalidade, body.concedido, body.versao_termo,
                                                    ip_origem(request)))


@router.get("/consentimentos", response_model=s.ConsentimentosOut, summary="Consentimentos vigentes e histórico")
def listar(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    vigentes, historico = fidelidade.consentimentos(db, user)
    return s.ConsentimentosOut(vigentes=[_cons(c) for c in vigentes], historico=[_cons(c) for c in historico])


@router.get("/saldo", response_model=s.SaldoOut, summary="Saldo de pontos")
def saldo(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return s.SaldoOut(pontos=fidelidade.saldo(db, user))


@router.get("/historico", response_model=s.Page[s.MovFidelidadeOut], summary="Extrato de pontos")
def historico(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
              user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    itens, total = fidelidade.historico(db, user, page, limit)
    return s.Page(items=[s.MovFidelidadeOut(id=m.id, tipo=m.tipo.value, pontos=m.pontos, pedido_id=m.pedido_id,
                                            criado_em=m.criado_em) for m in itens], page=page, limit=limit, total=total)
