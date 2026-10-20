from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db, ip_origem
from app.application import estoque
from app.infrastructure.db.models import Usuario

router = APIRouter(tags=["Estoque"])


@router.get("/unidades/{unidade_id}/estoque", response_model=list[s.EstoqueItemOut],
            summary="Saldo por produto na unidade (GERENTE/ADMIN)")
def saldo_unidade(unidade_id: int, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = estoque.listar_estoque(db, user, unidade_id)
    return [s.EstoqueItemOut(produto_id=p.id, nome=p.nome, quantidade=e.quantidade) for e, p in rows]


@router.post("/estoque/movimentos", response_model=s.MovimentoOut, status_code=201,
             summary="Registrar entrada, saída ou ajuste (GERENTE/ADMIN)")
def movimentar(body: s.MovimentoIn, request: Request, user: Usuario = Depends(get_current_user),
               db: Session = Depends(get_db)):
    mov, e = estoque.movimentar(db, user, body.unidade_id, body.produto_id, body.tipo, body.quantidade, body.motivo,
                                ip_origem(request))
    return s.MovimentoOut(movimento_id=mov.id, unidade_id=e.unidade_id, produto_id=e.produto_id,
                          saldo_atual=e.quantidade)
