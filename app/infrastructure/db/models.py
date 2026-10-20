"""Modelos ORM – correspondem às tabelas do DER (Figura 2 do relatório)."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer,
                        Numeric, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (CanalPedido, FinalidadeDados, PerfilUsuario, StatusPagamento, StatusPedido,
                              TipoDesconto, TipoMovimento, TipoPontos)
from app.infrastructure.db.base import Base


def agora() -> datetime:
    """Data/hora atual em UTC (naive – o serializador da API acrescenta o 'Z')."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enum(e):
    return Enum(e, native_enum=False, length=30, validate_strings=True)


Money = Numeric(10, 2)


class Unidade(Base):
    __tablename__ = "unidade"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2))
    cozinha_completa: Mapped[bool] = mapped_column(Boolean, default=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[PerfilUsuario] = mapped_column(_enum(PerfilUsuario))
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Cliente(Base):
    __tablename__ = "cliente"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), unique=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    anonimizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    usuario: Mapped[Usuario] = relationship()


class Consentimento(Base):
    __tablename__ = "consentimento"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    finalidade: Mapped[FinalidadeDados] = mapped_column(_enum(FinalidadeDados))
    concedido: Mapped[bool] = mapped_column(Boolean)
    versao_termo: Mapped[str] = mapped_column(String(20))
    registrado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Produto(Base):
    __tablename__ = "produto"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    categoria: Mapped[str] = mapped_column(String(60))
    preco_base: Mapped[Decimal] = mapped_column(Money)
    sazonal: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class CardapioUnidade(Base):
    __tablename__ = "cardapio_unidade"
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"), primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"), primary_key=True)
    preco_unidade: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)


class Estoque(Base):
    __tablename__ = "estoque"
    __table_args__ = (UniqueConstraint("unidade_id", "produto_id", name="uq_estoque_unidade_produto"),
                      CheckConstraint("quantidade >= 0", name="ck_estoque_quantidade_nao_negativa"))
    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"))
    quantidade: Mapped[int] = mapped_column(Integer, default=0)


class Pedido(Base):
    __tablename__ = "pedido"
    __table_args__ = (Index("ix_pedido_unidade_status_criado", "unidade_id", "status", "criado_em"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"), nullable=True, index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id"))
    canal_pedido: Mapped[CanalPedido] = mapped_column(_enum(CanalPedido), index=True)
    status: Mapped[StatusPedido] = mapped_column(_enum(StatusPedido))
    valor_bruto: Mapped[Decimal] = mapped_column(Money)
    desconto: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.00"))
    valor_total: Mapped[Decimal] = mapped_column(Money)
    pontos_resgatados: Mapped[int] = mapped_column(Integer, default=0)
    chave_idempotencia: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    itens: Mapped[list["ItemPedido"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    pagamentos: Mapped[list["Pagamento"]] = relationship(back_populates="pedido", order_by="Pagamento.id")


class ItemPedido(Base):
    __tablename__ = "item_pedido"
    __table_args__ = (CheckConstraint("quantidade > 0", name="ck_item_quantidade_positiva"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[Decimal] = mapped_column(Money)
    pedido: Mapped[Pedido] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship()


class MovimentoEstoque(Base):
    __tablename__ = "movimento_estoque"
    id: Mapped[int] = mapped_column(primary_key=True)
    estoque_id: Mapped[int] = mapped_column(ForeignKey("estoque.id"), index=True)
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedido.id"), nullable=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    tipo: Mapped[TipoMovimento] = mapped_column(_enum(TipoMovimento))
    quantidade: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Pagamento(Base):
    __tablename__ = "pagamento"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), index=True)
    forma_pagamento: Mapped[str] = mapped_column(String(30))
    status: Mapped[StatusPagamento] = mapped_column(_enum(StatusPagamento))
    valor: Mapped[Decimal] = mapped_column(Money)
    id_transacao_externa: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload_resposta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    pedido: Mapped[Pedido] = relationship(back_populates="pagamentos")


class MovimentoFidelidade(Base):
    __tablename__ = "movimento_fidelidade"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedido.id"), nullable=True)
    tipo: Mapped[TipoPontos] = mapped_column(_enum(TipoPontos))
    pontos: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Promocao(Base):
    __tablename__ = "promocao"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidade.id"), nullable=True)
    nome: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[TipoDesconto] = mapped_column(_enum(TipoDesconto))
    valor: Mapped[Decimal] = mapped_column(Money)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    exige_consentimento: Mapped[bool] = mapped_column(Boolean, default=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditoriaLog(Base):
    __tablename__ = "auditoria_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str] = mapped_column(String(40), index=True)
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
