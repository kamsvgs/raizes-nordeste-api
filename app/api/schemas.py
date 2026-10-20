"""Schemas (DTOs) de entrada e saída. JSON em camelCase; respostas nunca expõem dados sensíveis (API3)."""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.domain.enums import (CanalPedido, FinalidadeDados, PerfilUsuario, StatusPagamento, StatusPedido,
                              TipoDesconto, TipoMovimento)

Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
UtcDt = Annotated[datetime, PlainSerializer(lambda d: d.isoformat(timespec="seconds") + "Z", return_type=str)]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


T = TypeVar("T")


class Page(CamelModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total: int


# ------------------------------ entrada ------------------------------
class _ComEmail(CamelModel):
    email: str = Field(max_length=160)

    @field_validator("email")
    @classmethod
    def _valida_email(cls, v: str) -> str:
        if not _EMAIL.match(v):
            raise ValueError("E-mail em formato inválido")
        return v.strip().lower()


class RegistroIn(_ComEmail):
    model_config = ConfigDict(json_schema_extra={"examples": [{"nome": "Maria Souza", "email": "maria@exemplo.com", "senha": "Senha@123", "telefone": "81999990000"}]})
    nome: str = Field(min_length=2, max_length=120)
    senha: str = Field(min_length=8, max_length=72)
    telefone: str | None = Field(default=None, max_length=30)
    data_nascimento: date | None = None


class LoginIn(_ComEmail):
    model_config = ConfigDict(json_schema_extra={"examples": [{"email": "cliente@raizes.test", "senha": "Senha@123"}]})
    senha: str = Field(min_length=1, max_length=72)


class UsuarioInternoIn(_ComEmail):
    model_config = ConfigDict(json_schema_extra={"examples": [{"nome": "Carlos Lima", "email": "carlos@raizes.test", "senha": "Senha@123", "perfil": "ATENDENTE", "unidadeId": 1}]})
    nome: str = Field(min_length=2, max_length=120)
    senha: str = Field(min_length=8, max_length=72)
    perfil: PerfilUsuario
    unidade_id: int

    @field_validator("perfil")
    @classmethod
    def _perfil_interno(cls, v):
        if v not in (PerfilUsuario.ATENDENTE, PerfilUsuario.COZINHA, PerfilUsuario.GERENTE):
            raise ValueError("Perfil deve ser ATENDENTE, COZINHA ou GERENTE")
        return v


class UnidadeIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"nome": "Raízes Centro", "cidade": "Salvador", "uf": "BA", "cozinhaCompleta": False}]})
    nome: str = Field(min_length=2, max_length=120)
    cidade: str = Field(min_length=2, max_length=80)
    uf: str = Field(min_length=2, max_length=2)
    cozinha_completa: bool = True


class UnidadePatch(CamelModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    cidade: str | None = Field(default=None, min_length=2, max_length=80)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    cozinha_completa: bool | None = None
    ativa: bool | None = None


class ProdutoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"nome": "Tapioca de carne de sol", "descricao": "Tapioca recheada", "categoria": "Tapiocas", "precoBase": 16.5, "sazonal": False}]})
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=300)
    categoria: str = Field(min_length=2, max_length=60)
    preco_base: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    sazonal: bool = False


class CardapioItemIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"disponivel": True, "precoUnidade": 13.0}]})
    disponivel: bool = True
    preco_unidade: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class ItemPedidoIn(CamelModel):
    produto_id: int
    quantidade: int = Field(gt=0, le=1000)


class PedidoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"canalPedido": "TOTEM", "unidadeId": 1, "clienteId": 123, "itens": [{"produtoId": 10, "quantidade": 2}], "formaPagamento": "MOCK", "resgatarPontos": 0}]})
    canal_pedido: CanalPedido
    unidade_id: int
    cliente_id: int | None = None
    itens: list[ItemPedidoIn] = Field(min_length=1)
    forma_pagamento: str | None = None
    resgatar_pontos: int = Field(default=0, ge=0)


class StatusIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "EM_PREPARO"}]})
    status: StatusPedido


class CancelamentoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"motivo": "Cliente desistiu do pedido"}]})
    motivo: str = Field(min_length=3, max_length=200)


class PagamentoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"formaPagamento": "MOCK", "tokenCartao": "tok_aprovado"}]})
    forma_pagamento: str = Field(default="MOCK", max_length=30)
    token_cartao: str = Field(min_length=1, max_length=80)


class MovimentoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"unidadeId": 1, "produtoId": 10, "tipo": "ENTRADA", "quantidade": 50, "motivo": "Reposição semanal"}]})
    unidade_id: int
    produto_id: int
    tipo: TipoMovimento
    quantidade: int = Field(ge=0, le=100000)
    motivo: str = Field(min_length=3, max_length=200)

    @model_validator(mode="after")
    def _qtd(self):
        if self.tipo != TipoMovimento.AJUSTE and self.quantidade <= 0:
            raise ValueError("Quantidade deve ser maior que zero")
        return self


class ConsentimentoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"finalidade": "FIDELIDADE", "concedido": True, "versaoTermo": "2026-01"}]})
    finalidade: FinalidadeDados
    concedido: bool
    versao_termo: str = Field(default="2026-01", max_length=20)


class PromocaoIn(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"nome": "Terça nordestina", "tipo": "PERCENTUAL", "valor": 10, "inicio": "2026-10-01", "fim": "2026-12-31", "unidadeId": 1, "exigeConsentimento": False}]})
    nome: str = Field(min_length=2, max_length=120)
    tipo: TipoDesconto
    valor: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    inicio: date
    fim: date
    unidade_id: int | None = None
    exige_consentimento: bool = False

    @model_validator(mode="after")
    def _pct(self):
        if self.tipo == TipoDesconto.PERCENTUAL and self.valor > 100:
            raise ValueError("Percentual deve ser no máximo 100")
        return self


# ------------------------------ saída ------------------------------
class UsuarioOut(CamelModel):
    id: int
    nome: str
    email: str
    perfil: PerfilUsuario
    unidade_id: int | None = None


class TokenOut(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "accessToken": "eyJhbGciOiJIUzI1NiIs...", "tokenType": "Bearer", "expiresIn": 3600,
        "user": {"id": 10, "nome": "Cliente Exemplo", "email": "cliente@raizes.test", "perfil": "CLIENTE", "unidadeId": None}}]})
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UsuarioOut


class ClienteOut(CamelModel):
    id: int
    nome: str
    email: str
    telefone: str | None = None
    data_nascimento: date | None = None


class UnidadeOut(CamelModel):
    id: int
    nome: str
    cidade: str
    uf: str
    cozinha_completa: bool
    ativa: bool


class ProdutoOut(CamelModel):
    id: int
    nome: str
    descricao: str | None = None
    categoria: str
    preco_base: Money
    sazonal: bool
    ativo: bool


class CardapioItemOut(CamelModel):
    produto_id: int
    nome: str
    descricao: str | None = None
    categoria: str
    preco: Money
    sazonal: bool


class CardapioConfigOut(CamelModel):
    unidade_id: int
    produto_id: int
    disponivel: bool
    preco_unidade: Money | None = None


class EstoqueItemOut(CamelModel):
    produto_id: int
    nome: str
    quantidade: int


class MovimentoOut(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"movimentoId": 88, "unidadeId": 1, "produtoId": 10, "saldoAtual": 150}]})
    movimento_id: int
    unidade_id: int
    produto_id: int
    saldo_atual: int


class ItemPedidoOut(CamelModel):
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario: Money


class PedidoOut(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"id": 501, "canalPedido": "TOTEM", "status": "AGUARDANDO_PAGAMENTO", "unidadeId": 1, "clienteId": 7, "itens": [{"produtoId": 10, "nome": "Tapioca de queijo coalho", "quantidade": 2, "precoUnitario": 12.5}], "valorBruto": 25.0, "desconto": 0.0, "valorTotal": 25.0, "pontosResgatados": 0, "criadoEm": "2026-10-16T12:00:00Z", "atualizadoEm": "2026-10-16T12:00:00Z"}]})
    id: int
    canal_pedido: CanalPedido
    status: StatusPedido
    unidade_id: int
    cliente_id: int | None = None
    itens: list[ItemPedidoOut]
    valor_bruto: Money
    desconto: Money
    valor_total: Money
    pontos_resgatados: int
    criado_em: UtcDt
    atualizado_em: UtcDt


class PedidoResumoOut(CamelModel):
    id: int
    status: StatusPedido


class PagamentoOut(CamelModel):
    id: int
    status: StatusPagamento
    valor: Money
    forma_pagamento: str
    id_transacao_externa: str | None = None
    criado_em: UtcDt


class PagamentoRespostaOut(CamelModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"pedido": {"id": 501, "status": "PAGO"}, "pagamento": {"id": 9001, "status": "APROVADO", "valor": 25.0, "formaPagamento": "MOCK", "idTransacaoExterna": "mock-7f3a91c2", "criadoEm": "2026-10-16T12:01:00Z"}, "pontosCreditados": 25}]})
    pedido: PedidoResumoOut
    pagamento: PagamentoOut
    pontos_creditados: int


class ConsentimentoOut(CamelModel):
    finalidade: FinalidadeDados
    concedido: bool
    versao_termo: str
    registrado_em: UtcDt


class ConsentimentosOut(CamelModel):
    vigentes: list[ConsentimentoOut]
    historico: list[ConsentimentoOut]


class SaldoOut(CamelModel):
    pontos: int


class MovFidelidadeOut(CamelModel):
    id: int
    tipo: str
    pontos: int
    pedido_id: int | None = None
    criado_em: UtcDt


class PromocaoOut(CamelModel):
    id: int
    nome: str
    tipo: TipoDesconto
    valor: Money
    inicio: date
    fim: date
    unidade_id: int | None = None
    exige_consentimento: bool


class AuditoriaOut(CamelModel):
    id: int
    usuario_id: int | None = None
    acao: str
    entidade: str
    entidade_id: int | None = None
    detalhes: dict | None = None
    ip_origem: str | None = None
    criado_em: UtcDt


def pedido_out(p) -> PedidoOut:
    return PedidoOut(
        id=p.id, canal_pedido=p.canal_pedido, status=p.status, unidade_id=p.unidade_id, cliente_id=p.cliente_id,
        itens=[ItemPedidoOut(produto_id=i.produto_id, nome=i.produto.nome, quantidade=i.quantidade,
                             preco_unitario=i.preco_unitario) for i in p.itens],
        valor_bruto=p.valor_bruto, desconto=p.desconto, valor_total=p.valor_total,
        pontos_resgatados=p.pontos_resgatados, criado_em=p.criado_em, atualizado_em=p.atualizado_em)
