"""Casos de uso de pedido: criar, listar, atualizar status e cancelar (UC03, UC05, UC06, UC07)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.application.comum import cliente_do_usuario, exigir_perfil, pedido_ou_404
from app.domain import regras
from app.domain.enums import (CanalPedido, FinalidadeDados, PerfilUsuario as P, StatusPedido as S, TipoMovimento,
                              TipoPontos)
from app.domain.exceptions import AcessoNegado, Conflito, NaoEncontrado, ValidacaoNegocio
from app.infrastructure import auditoria
from app.infrastructure.db.models import (Cliente, ItemPedido, Pedido, Promocao, Unidade, Usuario, agora)
from app.infrastructure.db.repositorios import CardapioRepo, EstoqueRepo, FidelidadeRepo, PedidoRepo


@dataclass
class DadosPedido:
    canal: CanalPedido
    unidade_id: int
    cliente_id: int | None
    itens: list[tuple[int, int]]       # (produto_id, quantidade)
    resgatar_pontos: int = 0


def criar_pedido(db: Session, user: Usuario, dados: DadosPedido, chave: str | None, ip: str | None):
    """Retorna (pedido, criado). criado=False quando a chave de idempotência já existia (RN14)."""
    exigir_perfil(user, P.CLIENTE, P.ATENDENTE)
    pedidos = PedidoRepo(db)
    chave_completa = f"{user.id}:{chave}" if chave else None
    if chave_completa:
        existente = pedidos.por_chave(chave_completa)
        if existente:
            return existente, False

    unidade = db.get(Unidade, dados.unidade_id)
    if unidade is None or not unidade.ativa:
        raise NaoEncontrado("Unidade não encontrada.", "UNIDADE_NAO_ENCONTRADA")
    if user.perfil == P.ATENDENTE and user.unidade_id != unidade.id:
        raise AcessoNegado("Atendente só registra pedidos da própria unidade.")

    if user.perfil == P.CLIENTE:
        cliente = cliente_do_usuario(db, user)
    elif dados.cliente_id:
        cliente = db.get(Cliente, dados.cliente_id)
        if cliente is None:
            raise NaoEncontrado("Cliente não encontrado.", "CLIENTE_NAO_ENCONTRADO")
    else:
        cliente = None  # pedido de balcão sem identificação (premissa A3)

    # junta itens repetidos
    qtds: dict[int, int] = defaultdict(int)
    for pid, q in dados.itens:
        qtds[pid] += q

    cardapio, estoque = CardapioRepo(db), EstoqueRepo(db)
    linhas = []  # (produto, quantidade, preco)
    for pid, q in qtds.items():
        achado = cardapio.item_disponivel(unidade.id, pid)  # RN02
        if not achado:
            raise NaoEncontrado(f"Produto {pid} não está disponível no cardápio da unidade.",
                                "PRODUTO_NAO_ENCONTRADO",
                                [{"field": "itens.produtoId", "issue": f"Produto {pid} indisponível nesta unidade"}])
        card, prod = achado
        preco = card.preco_unidade if card.preco_unidade is not None else prod.preco_base  # RN03
        linhas.append((prod, q, preco))

    faltas = []
    for i, (prod, q, _) in enumerate(linhas):
        saldo = estoque.saldo(unidade.id, prod.id)
        if saldo < q:
            faltas.append({"field": f"itens[{i}].quantidade", "issue": f"Disponível: {saldo}"})
    if faltas:
        raise Conflito("Não há quantidade suficiente para um ou mais itens.", "ESTOQUE_INSUFICIENTE", faltas)

    bruto = sum((p * q for _, q, p in linhas), Decimal("0.00"))
    fid = FidelidadeRepo(db)

    # promoções (RN10): escolhe a de maior desconto
    desc_promo = Decimal("0.00")
    hoje = date.today()
    promos = db.scalars(select(Promocao).where(Promocao.ativa.is_(True), Promocao.inicio <= hoje,
                                               Promocao.fim >= hoje,
                                               (Promocao.unidade_id.is_(None)) | (Promocao.unidade_id == unidade.id))).all()
    for pr in promos:
        if pr.exige_consentimento and not (cliente and fid.consentimento_ativo(cliente.id, FinalidadeDados.SEGMENTACAO)):
            continue
        desc_promo = max(desc_promo, regras.desconto_promocao(pr.tipo, pr.valor, bruto))

    # resgate de pontos (RN09)
    desc_resgate = Decimal("0.00")
    pontos = dados.resgatar_pontos
    if pontos > 0:
        if cliente is None:
            raise ValidacaoNegocio("Resgate de pontos exige cliente identificado.", "PONTOS_INVALIDOS")
        if not fid.consentimento_ativo(cliente.id, FinalidadeDados.FIDELIDADE):
            raise Conflito("É necessário consentimento ativo de FIDELIDADE para resgatar pontos.",
                           "CONSENTIMENTO_AUSENTE")
        if pontos % regras.PONTOS_PARA_RESGATE != 0:
            raise ValidacaoNegocio(f"Os pontos devem ser múltiplos de {regras.PONTOS_PARA_RESGATE}.", "PONTOS_INVALIDOS")
        if fid.saldo(cliente.id) < pontos:
            raise Conflito("Saldo de pontos insuficiente.", "PONTOS_INSUFICIENTES")
        desc_resgate = regras.desconto_resgate(pontos)
        if desc_resgate > regras.limite_desconto_resgate(bruto - desc_promo):
            raise ValidacaoNegocio("O resgate excede 50% do valor do pedido.", "RESGATE_ACIMA_DO_LIMITE")

    desconto = desc_promo + desc_resgate
    pedido = Pedido(cliente_id=cliente.id if cliente else None, unidade_id=unidade.id, canal_pedido=dados.canal,
                    status=S.AGUARDANDO_PAGAMENTO, valor_bruto=bruto, desconto=desconto,
                    valor_total=bruto - desconto, pontos_resgatados=pontos, chave_idempotencia=chave_completa)
    for prod, q, preco in linhas:
        pedido.itens.append(ItemPedido(produto_id=prod.id, quantidade=q, preco_unitario=preco))
    db.add(pedido)
    db.flush()

    for prod, q, _ in linhas:
        if not estoque.baixar(unidade.id, prod.id, q):  # proteção contra corrida (D4)
            raise Conflito("Não há quantidade suficiente para um ou mais itens.", "ESTOQUE_INSUFICIENTE")
        estoque.movimento(estoque.obter(unidade.id, prod.id), user.id, TipoMovimento.SAIDA, q,
                          f"Venda – pedido {pedido.id}", pedido.id)
    if pontos > 0:
        fid.adicionar(cliente.id, pedido.id, TipoPontos.RESGATE, -pontos)

    auditoria.registrar(db, user.id, "PEDIDO_CRIADO", "pedido", pedido.id,
                        {"canalPedido": dados.canal.value, "unidadeId": unidade.id,
                         "valorTotal": str(pedido.valor_total)}, ip)
    db.commit()
    return pedido, True


def listar_pedidos(db: Session, user: Usuario, canal: CanalPedido | None, status: S | None,
                   unidade_id: int | None, page: int, limit: int):
    q = select(Pedido)
    if user.perfil == P.CLIENTE:
        c = cliente_do_usuario(db, user)
        q = q.where(Pedido.cliente_id == (c.id if c else -1))
    elif user.perfil != P.ADMIN:
        q = q.where(Pedido.unidade_id == user.unidade_id)
    if canal:
        q = q.where(Pedido.canal_pedido == canal)
    if status:
        q = q.where(Pedido.status == status)
    if unidade_id:
        q = q.where(Pedido.unidade_id == unidade_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    itens = db.scalars(q.options(selectinload(Pedido.itens)).order_by(Pedido.id.desc())
                       .offset((page - 1) * limit).limit(limit)).all()
    return itens, int(total or 0)


def obter_pedido(db: Session, user: Usuario, pedido_id: int) -> Pedido:
    return pedido_ou_404(db, user, PedidoRepo(db).obter(pedido_id))


def atualizar_status(db: Session, user: Usuario, pedido_id: int, novo: S, ip: str | None) -> Pedido:
    exigir_perfil(user, P.COZINHA, P.ATENDENTE, P.GERENTE, P.ADMIN)
    pedido = pedido_ou_404(db, user, PedidoRepo(db).obter(pedido_id))
    if not regras.transicao_valida(pedido.status, novo):  # RN05
        raise Conflito(f"Não é possível mudar de {pedido.status.value} para {novo.value}.", "TRANSICAO_INVALIDA")
    if user.perfil not in regras.perfis_da_transicao(pedido.status, novo):
        raise AcessoNegado("Seu perfil não pode executar esta transição de status.")
    anterior = pedido.status
    pedido.status = novo
    pedido.atualizado_em = agora()
    auditoria.registrar(db, user.id, "PEDIDO_STATUS_ALTERADO", "pedido", pedido.id,
                        {"de": anterior.value, "para": novo.value}, ip)
    db.commit()
    return pedido


def reverter_pedido(db: Session, pedido: Pedido, usuario_id: int, motivo: str) -> None:
    """Cancela o pedido devolvendo estoque e estornando pontos (RN04, RN07, RN11)."""
    estoque, fid = EstoqueRepo(db), FidelidadeRepo(db)
    for it in pedido.itens:
        e = estoque.repor(pedido.unidade_id, it.produto_id, it.quantidade)
        estoque.movimento(e, usuario_id, TipoMovimento.ENTRADA, it.quantidade, f"Devolução – {motivo}", pedido.id)
    if pedido.cliente_id:
        if pedido.pontos_resgatados:
            fid.adicionar(pedido.cliente_id, pedido.id, TipoPontos.ACUMULO, pedido.pontos_resgatados)
        ganhos = fid.acumulado_no_pedido(pedido.id)
        if ganhos > 0:
            fid.adicionar(pedido.cliente_id, pedido.id, TipoPontos.ACUMULO, -ganhos)
    pedido.status = S.CANCELADO
    pedido.atualizado_em = agora()


def cancelar_pedido(db: Session, user: Usuario, pedido_id: int, motivo: str, ip: str | None) -> Pedido:
    if user.perfil == P.COZINHA:
        raise AcessoNegado("A cozinha não cancela pedidos.")
    pedido = pedido_ou_404(db, user, PedidoRepo(db).obter(pedido_id))
    if pedido.status not in (S.AGUARDANDO_PAGAMENTO, S.PAGO, S.EM_PREPARO):
        raise Conflito(f"Não é possível cancelar um pedido {pedido.status.value}.", "TRANSICAO_INVALIDA")
    if not regras.pode_cancelar(pedido.status, user.perfil):  # RN11
        raise AcessoNegado("Pedidos já pagos só podem ser cancelados por gerente ou administrador.")
    anterior = pedido.status
    reverter_pedido(db, pedido, user.id, f"cancelamento do pedido {pedido.id}")
    auditoria.registrar(db, user.id, "PEDIDO_CANCELADO", "pedido", pedido.id,
                        {"de": anterior.value, "motivo": motivo}, ip)
    db.commit()
    return pedido
