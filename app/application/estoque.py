"""Casos de uso de estoque por unidade (UC09)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.comum import exigir_perfil, exigir_unidade
from app.domain.enums import PerfilUsuario as P, TipoMovimento as T
from app.domain.exceptions import Conflito, NaoEncontrado
from app.infrastructure import auditoria
from app.infrastructure.db.models import Estoque, Produto, Unidade, Usuario
from app.infrastructure.db.repositorios import EstoqueRepo


def movimentar(db: Session, user: Usuario, unidade_id: int, produto_id: int, tipo: T, quantidade: int,
               motivo: str, ip: str | None):
    exigir_perfil(user, P.GERENTE, P.ADMIN)
    exigir_unidade(user, unidade_id)
    if db.get(Unidade, unidade_id) is None:
        raise NaoEncontrado("Unidade não encontrada.", "UNIDADE_NAO_ENCONTRADA")
    if db.get(Produto, produto_id) is None:
        raise NaoEncontrado("Produto não encontrado.", "PRODUTO_NAO_ENCONTRADO")
    repo = EstoqueRepo(db)
    if tipo == T.ENTRADA:
        e = repo.repor(unidade_id, produto_id, quantidade)
    elif tipo == T.SAIDA:
        saldo = repo.saldo(unidade_id, produto_id)
        if quantidade > saldo or not repo.baixar(unidade_id, produto_id, quantidade):
            raise Conflito("Saída maior que o saldo em estoque.", "ESTOQUE_INSUFICIENTE",
                           [{"field": "quantidade", "issue": f"Disponível: {saldo}"}])
        e = repo.obter(unidade_id, produto_id)
        db.refresh(e)
    else:  # AJUSTE: define o saldo absoluto
        e = repo.definir(unidade_id, produto_id, quantidade)
    mov = repo.movimento(e, user.id, tipo, quantidade, motivo)
    auditoria.registrar(db, user.id, "ESTOQUE_MOVIMENTADO", "estoque", e.id,
                        {"tipo": tipo.value, "quantidade": quantidade, "saldoAtual": e.quantidade, "motivo": motivo}, ip)
    db.commit()
    return mov, e


def listar_estoque(db: Session, user: Usuario, unidade_id: int):
    exigir_perfil(user, P.GERENTE, P.ADMIN)
    exigir_unidade(user, unidade_id)
    if db.get(Unidade, unidade_id) is None:
        raise NaoEncontrado("Unidade não encontrada.", "UNIDADE_NAO_ENCONTRADA")
    return db.execute(select(Estoque, Produto).join(Produto, Produto.id == Estoque.produto_id)
                      .where(Estoque.unidade_id == unidade_id).order_by(Produto.nome)).all()
