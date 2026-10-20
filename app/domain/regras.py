"""Regras de negócio puras (sem dependência de framework ou banco)."""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from app.domain.enums import PerfilUsuario as P, StatusPedido as S, TipoDesconto

CENT = Decimal("0.01")

# RN05 – máquina de estados: (origem, destino) -> perfis autorizados a executar a transição
TRANSICOES: dict[tuple[S, S], set[P]] = {
    (S.PAGO, S.EM_PREPARO): {P.COZINHA, P.ATENDENTE, P.GERENTE, P.ADMIN},
    (S.EM_PREPARO, S.PRONTO): {P.COZINHA, P.GERENTE, P.ADMIN},
    (S.PRONTO, S.ENTREGUE): {P.ATENDENTE, P.GERENTE, P.ADMIN},
}

PONTOS_POR_REAL = 1                   # RN08
PONTOS_PARA_RESGATE = 100             # RN09
VALOR_RESGATE = Decimal("5.00")       # RN09
LIMITE_RESGATE = Decimal("0.50")      # RN09


def transicao_valida(origem: S, destino: S) -> bool:
    return (origem, destino) in TRANSICOES


def perfis_da_transicao(origem: S, destino: S) -> set[P]:
    return TRANSICOES[(origem, destino)]


def pode_cancelar(status: S, perfil: P) -> bool:
    """RN11: aguardando pagamento – dono/atendimento/gerência; pago ou em preparo – somente gerente/admin."""
    if status == S.AGUARDANDO_PAGAMENTO:
        return perfil in {P.CLIENTE, P.ATENDENTE, P.GERENTE, P.ADMIN}
    if status in {S.PAGO, S.EM_PREPARO}:
        return perfil in {P.GERENTE, P.ADMIN}
    return False


def calcular_pontos(valor_pago: Decimal) -> int:
    """RN08: 1 ponto por R$ 1,00 pago, arredondado para baixo."""
    return int((valor_pago * PONTOS_POR_REAL).to_integral_value(rounding=ROUND_DOWN))


def desconto_resgate(pontos: int) -> Decimal:
    """RN09: 100 pontos = R$ 5,00."""
    return (Decimal(pontos // PONTOS_PARA_RESGATE) * VALOR_RESGATE).quantize(CENT)


def limite_desconto_resgate(base: Decimal) -> Decimal:
    return (base * LIMITE_RESGATE).quantize(CENT, rounding=ROUND_DOWN)


def desconto_promocao(tipo: TipoDesconto, valor: Decimal, base: Decimal) -> Decimal:
    """RN10: desconto nunca excede a base."""
    d = base * valor / Decimal("100") if tipo == TipoDesconto.PERCENTUAL else valor
    return min(d.quantize(CENT, rounding=ROUND_HALF_UP), base)
