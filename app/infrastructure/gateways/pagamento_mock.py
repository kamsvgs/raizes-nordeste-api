"""Gateway de pagamento simulado (mock) – implementa a porta PagamentoGateway.

Tokens de teste:
  tok_aprovado -> APROVADO
  tok_recusado -> RECUSADO
  tok_timeout  -> sem resposta no prazo (GatewayIndisponivel)
  qualquer outro -> RECUSADO (token desconhecido)
"""
import uuid
from decimal import Decimal

from app.domain.enums import StatusPagamento
from app.domain.exceptions import GatewayIndisponivel
from app.domain.ports import PagamentoGateway, ResultadoGateway


class PagamentoGatewayMock(PagamentoGateway):
    def autorizar(self, valor: Decimal, token: str, id_requisicao: str) -> ResultadoGateway:
        if token == "tok_timeout":
            raise GatewayIndisponivel(
                "Gateway sem resposta. O pedido continua aguardando pagamento; tente novamente.")
        id_tx = f"mock-{uuid.uuid4().hex[:8]}"
        if token == "tok_aprovado":
            return ResultadoGateway(StatusPagamento.APROVADO, id_tx,
                                    {"codigo": "00", "mensagem": "Transação aprovada", "valor": str(valor)})
        motivo = "Recusado pelo emissor (mock)" if token == "tok_recusado" else "Token desconhecido (mock)"
        return ResultadoGateway(StatusPagamento.RECUSADO, id_tx, {"codigo": "51", "mensagem": motivo})
