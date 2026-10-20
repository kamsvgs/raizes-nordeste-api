"""Repositórios SQLAlchemy – consultas e operações de persistência usadas pela camada Application."""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import FinalidadeDados, TipoMovimento, TipoPontos
from app.infrastructure.db.models import (CardapioUnidade, Cliente, Consentimento, Estoque, MovimentoEstoque,
                                          MovimentoFidelidade, Pedido, Produto, Usuario, agora)


class EstoqueRepo:
    def __init__(self, db: Session):
        self.db = db

    def obter(self, unidade_id: int, produto_id: int) -> Estoque | None:
        return self.db.scalar(select(Estoque).where(Estoque.unidade_id == unidade_id,
                                                    Estoque.produto_id == produto_id))

    def saldo(self, unidade_id: int, produto_id: int) -> int:
        e = self.obter(unidade_id, produto_id)
        return e.quantidade if e else 0

    def baixar(self, unidade_id: int, produto_id: int, qtd: int) -> bool:
        """Baixa atômica (decisão D4): só atualiza se houver saldo suficiente."""
        res = self.db.execute(
            update(Estoque)
            .where(Estoque.unidade_id == unidade_id, Estoque.produto_id == produto_id, Estoque.quantidade >= qtd)
            .values(quantidade=Estoque.quantidade - qtd))
        return res.rowcount == 1

    def repor(self, unidade_id: int, produto_id: int, qtd: int) -> Estoque:
        e = self.obter(unidade_id, produto_id)
        if e is None:
            e = Estoque(unidade_id=unidade_id, produto_id=produto_id, quantidade=0)
            self.db.add(e)
            self.db.flush()
        self.db.execute(update(Estoque).where(Estoque.id == e.id).values(quantidade=Estoque.quantidade + qtd))
        self.db.refresh(e)
        return e

    def definir(self, unidade_id: int, produto_id: int, qtd: int) -> Estoque:
        e = self.obter(unidade_id, produto_id)
        if e is None:
            e = Estoque(unidade_id=unidade_id, produto_id=produto_id, quantidade=qtd)
            self.db.add(e)
        else:
            e.quantidade = qtd
        self.db.flush()
        return e

    def movimento(self, estoque: Estoque, usuario_id: int, tipo: TipoMovimento, qtd: int, motivo: str,
                  pedido_id: int | None = None) -> MovimentoEstoque:
        m = MovimentoEstoque(estoque_id=estoque.id, usuario_id=usuario_id, tipo=tipo, quantidade=qtd,
                             motivo=motivo, pedido_id=pedido_id, criado_em=agora())
        self.db.add(m)
        self.db.flush()
        return m


class FidelidadeRepo:
    def __init__(self, db: Session):
        self.db = db

    def consentimento_ativo(self, cliente_id: int, finalidade: FinalidadeDados) -> bool:
        ult = self.db.scalar(select(Consentimento).where(Consentimento.cliente_id == cliente_id,
                                                         Consentimento.finalidade == finalidade)
                             .order_by(Consentimento.id.desc()).limit(1))
        return bool(ult and ult.concedido)

    def saldo(self, cliente_id: int) -> int:
        return int(self.db.scalar(select(func.coalesce(func.sum(MovimentoFidelidade.pontos), 0))
                                  .where(MovimentoFidelidade.cliente_id == cliente_id)) or 0)

    def adicionar(self, cliente_id: int, pedido_id: int | None, tipo: TipoPontos, pontos: int) -> None:
        self.db.add(MovimentoFidelidade(cliente_id=cliente_id, pedido_id=pedido_id, tipo=tipo, pontos=pontos))
        self.db.flush()

    def acumulado_no_pedido(self, pedido_id: int) -> int:
        return int(self.db.scalar(select(func.coalesce(func.sum(MovimentoFidelidade.pontos), 0))
                                  .where(MovimentoFidelidade.pedido_id == pedido_id,
                                         MovimentoFidelidade.tipo == TipoPontos.ACUMULO)) or 0)


class ClienteRepo:
    def __init__(self, db: Session):
        self.db = db

    def do_usuario(self, usuario: Usuario) -> Cliente | None:
        return self.db.scalar(select(Cliente).where(Cliente.usuario_id == usuario.id))


class CardapioRepo:
    def __init__(self, db: Session):
        self.db = db

    def item_disponivel(self, unidade_id: int, produto_id: int):
        return self.db.execute(
            select(CardapioUnidade, Produto).join(Produto, Produto.id == CardapioUnidade.produto_id)
            .where(CardapioUnidade.unidade_id == unidade_id, CardapioUnidade.produto_id == produto_id,
                   CardapioUnidade.disponivel.is_(True), Produto.ativo.is_(True))).first()


class PedidoRepo:
    def __init__(self, db: Session):
        self.db = db

    def obter(self, pedido_id: int) -> Pedido | None:
        return self.db.scalar(select(Pedido).options(selectinload(Pedido.itens), selectinload(Pedido.pagamentos))
                              .where(Pedido.id == pedido_id))

    def por_chave(self, chave: str) -> Pedido | None:
        return self.db.scalar(select(Pedido).options(selectinload(Pedido.itens)).where(Pedido.chave_idempotencia == chave))
