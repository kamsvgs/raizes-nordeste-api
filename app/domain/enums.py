"""Enumerações do domínio (valores usados na API e no banco)."""
from enum import Enum


class CanalPedido(str, Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class PerfilUsuario(str, Enum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"
    ADMIN = "ADMIN"


class StatusPagamento(str, Enum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    ERRO_GATEWAY = "ERRO_GATEWAY"


class FinalidadeDados(str, Enum):
    FIDELIDADE = "FIDELIDADE"
    MARKETING = "MARKETING"
    SEGMENTACAO = "SEGMENTACAO"


class TipoMovimento(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AJUSTE = "AJUSTE"


class TipoPontos(str, Enum):
    ACUMULO = "ACUMULO"
    RESGATE = "RESGATE"
    EXPIRACAO = "EXPIRACAO"


class TipoDesconto(str, Enum):
    PERCENTUAL = "PERCENTUAL"
    VALOR = "VALOR"
