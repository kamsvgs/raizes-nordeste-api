from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db, get_gateway, ip_origem
from app.application import pagamentos, pedidos
from app.domain.enums import CanalPedido, StatusPedido
from app.domain.ports import PagamentoGateway
from app.infrastructure.db.models import Usuario

router = APIRouter(tags=["Pedidos e pagamentos"])


@router.post("/pedidos", response_model=s.PedidoOut, status_code=201, summary="Criar pedido (canalPedido obrigatório)")
def criar_pedido(body: s.PedidoIn, request: Request, response: Response,
                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
                 user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    dados = pedidos.DadosPedido(canal=body.canal_pedido, unidade_id=body.unidade_id, cliente_id=body.cliente_id,
                                itens=[(i.produto_id, i.quantidade) for i in body.itens],
                                resgatar_pontos=body.resgatar_pontos)
    pedido, criado = pedidos.criar_pedido(db, user, dados, idempotency_key, ip_origem(request))
    if not criado:
        response.status_code = 200  # RN14: repetição com a mesma chave devolve o pedido original
    return s.pedido_out(pedido)


@router.get("/pedidos", response_model=s.Page[s.PedidoOut], summary="Listar pedidos (filtros e paginação)")
def listar(canal_pedido: CanalPedido | None = Query(None, alias="canalPedido"),
           status: StatusPedido | None = None, unidade_id: int | None = Query(None, alias="unidadeId"),
           page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
           user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    itens, total = pedidos.listar_pedidos(db, user, canal_pedido, status, unidade_id, page, limit)
    return s.Page(items=[s.pedido_out(p) for p in itens], page=page, limit=limit, total=total)


@router.get("/pedidos/{pedido_id}", response_model=s.PedidoOut, summary="Consultar pedido")
def obter(pedido_id: int, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return s.pedido_out(pedidos.obter_pedido(db, user, pedido_id))


@router.patch("/pedidos/{pedido_id}/status", summary="Atualizar status do pedido")
def atualizar_status(pedido_id: int, body: s.StatusIn, request: Request, user: Usuario = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    p = pedidos.atualizar_status(db, user, pedido_id, body.status, ip_origem(request))
    return {"id": p.id, "status": p.status.value, "atualizadoEm": p.atualizado_em.isoformat(timespec="seconds") + "Z"}


@router.post("/pedidos/{pedido_id}/cancelamento", response_model=s.PedidoOut, summary="Cancelar pedido")
def cancelar(pedido_id: int, body: s.CancelamentoIn, request: Request, user: Usuario = Depends(get_current_user),
             db: Session = Depends(get_db)):
    return s.pedido_out(pedidos.cancelar_pedido(db, user, pedido_id, body.motivo, ip_origem(request)))


@router.post("/pedidos/{pedido_id}/pagamento", response_model=s.PagamentoRespostaOut,
             summary="Solicitar pagamento ao gateway (mock)")
def pagar(pedido_id: int, body: s.PagamentoIn, request: Request, user: Usuario = Depends(get_current_user),
          db: Session = Depends(get_db), gateway: PagamentoGateway = Depends(get_gateway)):
    pedido, pag, pontos = pagamentos.solicitar_pagamento(db, gateway, user, pedido_id, body.forma_pagamento,
                                                         body.token_cartao, ip_origem(request))
    return s.PagamentoRespostaOut(pedido=s.PedidoResumoOut(id=pedido.id, status=pedido.status),
                                  pagamento=s.PagamentoOut.model_validate(pag), pontos_creditados=pontos)


@router.get("/pedidos/{pedido_id}/pagamento", response_model=s.PagamentoOut, summary="Consultar pagamento do pedido")
def consultar_pagamento(pedido_id: int, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return pagamentos.pagamento_do_pedido(db, user, pedido_id)
