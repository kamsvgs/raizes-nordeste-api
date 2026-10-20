"""Portas (interfaces) que a infraestrutura implementa – inversão de dependência."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.enums import StatusPagamento


@dataclass
class ResultadoGateway:
    status: StatusPagamento            # APROVADO ou RECUSADO
    id_transacao: str
    payload: dict = field(default_factory=dict)


class PagamentoGateway(ABC):
    @abstractmethod
    def autorizar(self, valor: Decimal, token: str, id_requisicao: str) -> ResultadoGateway:
        """Autoriza a cobrança. Deve levantar GatewayIndisponivel em caso de timeout/erro de comunicação."""
