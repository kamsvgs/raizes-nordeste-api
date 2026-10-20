"""Caso de uso UC04 – Solicitar pagamento ao gateway (mock) e atualizar o pedido."""
import uuid

from sqlalchemy.orm import Session

from app.application.comum import exigir_perfil, pedido_ou_404
from app.application.pedidos import reverter_pedido
from app.domain import regras
from app.domain.enums import FinalidadeDados, PerfilUsuario as P, StatusPagamento, StatusPedido as S, TipoPontos
from app.domain.exceptions import Conflito, GatewayIndisponivel, NaoEncontrado, PagamentoRecusado
from app.domain.ports import PagamentoGateway
from app.infrastructure import auditoria
from app.infrastructure.db.models import Pagamento, Usuario, agora
from app.infrastructure.db.repositorios import FidelidadeRepo, PedidoRepo


def solicitar_pagamento(db: Session, gateway: PagamentoGateway, user: Usuario, pedido_id: int,
                        forma: str, token: str, ip: str | None):
    exigir_perfil(user, P.CLIENTE, P.ATENDENTE)
    pedido = pedido_ou_404(db, user, PedidoRepo(db).obter(pedido_id))
    if pedido.status != S.AGUARDANDO_PAGAMENTO:  # RN06
        raise Conflito(f"O pedido está {pedido.status.value} e não aguarda pagamento.",
                       "PEDIDO_NAO_AGUARDA_PAGAMENTO")

    id_req = f"pedido-{pedido.id}-{uuid.uuid4().hex[:8]}"
    try:
        res = gateway.autorizar(pedido.valor_total, token, id_req)
    except GatewayIndisponivel:
        db.add(Pagamento(pedido_id=pedido.id, forma_pagamento=forma, status=StatusPagamento.ERRO_GATEWAY,
                         valor=pedido.valor_total, payload_resposta={"erro": "timeout", "idRequisicao": id_req}))
        auditoria.registrar(db, user.id, "PAGAMENTO_ERRO_GATEWAY", "pedido", pedido.id, {"idRequisicao": id_req}, ip)
        db.commit()  # mantém o registro da falha; o pedido segue aguardando pagamento (RN07)
        raise

    pag = Pagamento(pedido_id=pedido.id, forma_pagamento=forma, status=res.status, valor=pedido.valor_total,
                    id_transacao_externa=res.id_transacao, payload_resposta=res.payload)
    db.add(pag)
    db.flush()

    if res.status == StatusPagamento.APROVADO:
        pedido.status = S.PAGO
        pedido.atualizado_em = agora()
        pontos = 0
        if pedido.cliente_id:
            fid = FidelidadeRepo(db)
            if fid.consentimento_ativo(pedido.cliente_id, FinalidadeDados.FIDELIDADE):  # RN08
                pontos = regras.calcular_pontos(pedido.valor_total)
                if pontos > 0:
                    fid.adicionar(pedido.cliente_id, pedido.id, TipoPontos.ACUMULO, pontos)
        auditoria.registrar(db, user.id, "PAGAMENTO_APROVADO", "pedido", pedido.id,
                            {"idTransacao": res.id_transacao, "pontos": pontos}, ip)
        db.commit()
        return pedido, pag, pontos

    # recusado (RN07): cancela o pedido e devolve estoque
    reverter_pedido(db, pedido, user.id, f"pagamento recusado do pedido {pedido.id}")
    auditoria.registrar(db, user.id, "PAGAMENTO_RECUSADO", "pedido", pedido.id, {"idTransacao": res.id_transacao}, ip)
    db.commit()
    raise PagamentoRecusado("Pagamento recusado pelo gateway.",
                            details=[{"field": "tokenCartao", "issue": res.payload.get("mensagem", "Recusado")}])


def pagamento_do_pedido(db: Session, user: Usuario, pedido_id: int) -> Pagamento:
    pedido = pedido_ou_404(db, user, PedidoRepo(db).obter(pedido_id))
    if not pedido.pagamentos:
        raise NaoEncontrado("Nenhum pagamento registrado para este pedido.", "PAGAMENTO_NAO_ENCONTRADO")
    return pedido.pagamentos[-1]
