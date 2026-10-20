"""Casos de uso de catálogo: unidades, produtos, cardápio e promoções (UC02, UC08, UC11)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.comum import exigir_perfil, exigir_unidade
from app.domain.enums import PerfilUsuario as P
from app.domain.exceptions import AcessoNegado, NaoEncontrado, ValidacaoNegocio
from app.infrastructure import auditoria
from app.infrastructure.db.models import CardapioUnidade, Produto, Promocao, Unidade, Usuario


def _paginar(db: Session, base, page: int, limit: int, ordem):
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    return db.execute(base.order_by(ordem).offset((page - 1) * limit).limit(limit)).all(), int(total or 0)


# ---- unidades ----
def listar_unidades(db: Session, page: int, limit: int):
    rows, total = _paginar(db, select(Unidade).where(Unidade.ativa.is_(True)), page, limit, Unidade.id)
    return [r[0] for r in rows], total


def obter_unidade(db: Session, unidade_id: int, somente_ativa: bool = True) -> Unidade:
    u = db.get(Unidade, unidade_id)
    if u is None or (somente_ativa and not u.ativa):
        raise NaoEncontrado("Unidade não encontrada.", "UNIDADE_NAO_ENCONTRADA")
    return u


def criar_unidade(db: Session, user: Usuario, dados: dict, ip: str | None) -> Unidade:
    exigir_perfil(user, P.ADMIN)
    u = Unidade(**dados)
    db.add(u)
    db.flush()
    auditoria.registrar(db, user.id, "UNIDADE_CRIADA", "unidade", u.id, {"nome": u.nome}, ip)
    db.commit()
    return u


def atualizar_unidade(db: Session, user: Usuario, unidade_id: int, dados: dict, ip: str | None) -> Unidade:
    exigir_perfil(user, P.ADMIN)
    u = obter_unidade(db, unidade_id, somente_ativa=False)
    for k, v in dados.items():
        setattr(u, k, v)
    auditoria.registrar(db, user.id, "UNIDADE_ATUALIZADA", "unidade", u.id, dados, ip)
    db.commit()
    return u


# ---- produtos ----
def listar_produtos(db: Session, page: int, limit: int, categoria: str | None):
    q = select(Produto).where(Produto.ativo.is_(True))
    if categoria:
        q = q.where(Produto.categoria == categoria)
    rows, total = _paginar(db, q, page, limit, Produto.id)
    return [r[0] for r in rows], total


def obter_produto(db: Session, produto_id: int) -> Produto:
    p = db.get(Produto, produto_id)
    if p is None or not p.ativo:
        raise NaoEncontrado("Produto não encontrado.", "PRODUTO_NAO_ENCONTRADO")
    return p


def criar_produto(db: Session, user: Usuario, dados: dict, ip: str | None) -> Produto:
    exigir_perfil(user, P.ADMIN)
    p = Produto(**dados)
    db.add(p)
    db.flush()
    auditoria.registrar(db, user.id, "PRODUTO_CRIADO", "produto", p.id, {"nome": p.nome}, ip)
    db.commit()
    return p


def atualizar_produto(db: Session, user: Usuario, produto_id: int, dados: dict, ip: str | None) -> Produto:
    exigir_perfil(user, P.ADMIN)
    p = obter_produto(db, produto_id)
    for k, v in dados.items():
        setattr(p, k, v)
    auditoria.registrar(db, user.id, "PRODUTO_ATUALIZADO", "produto", p.id, {k: str(v) for k, v in dados.items()}, ip)
    db.commit()
    return p


def inativar_produto(db: Session, user: Usuario, produto_id: int, ip: str | None) -> None:
    exigir_perfil(user, P.ADMIN)
    p = obter_produto(db, produto_id)
    p.ativo = False
    auditoria.registrar(db, user.id, "PRODUTO_INATIVADO", "produto", p.id, {}, ip)
    db.commit()


# ---- cardápio ----
def cardapio(db: Session, unidade_id: int, page: int, limit: int, categoria: str | None):
    obter_unidade(db, unidade_id)
    q = (select(CardapioUnidade, Produto).join(Produto, Produto.id == CardapioUnidade.produto_id)
         .where(CardapioUnidade.unidade_id == unidade_id, CardapioUnidade.disponivel.is_(True), Produto.ativo.is_(True)))
    if categoria:
        q = q.where(Produto.categoria == categoria)
    return _paginar(db, q, page, limit, Produto.id)


def definir_item_cardapio(db: Session, user: Usuario, unidade_id: int, produto_id: int, disponivel: bool,
                          preco, ip: str | None):
    exigir_perfil(user, P.GERENTE, P.ADMIN)
    exigir_unidade(user, unidade_id)
    obter_unidade(db, unidade_id, somente_ativa=False)
    obter_produto(db, produto_id)
    item = db.get(CardapioUnidade, (unidade_id, produto_id))
    if item is None:
        item = CardapioUnidade(unidade_id=unidade_id, produto_id=produto_id)
        db.add(item)
    item.disponivel, item.preco_unidade = disponivel, preco
    auditoria.registrar(db, user.id, "CARDAPIO_ATUALIZADO", "cardapio_unidade", produto_id,
                        {"unidadeId": unidade_id, "disponivel": disponivel, "preco": str(preco)}, ip)
    db.commit()
    return item


# ---- promoções ----
def promocoes_vigentes(db: Session, unidade_id: int | None):
    hoje = date.today()
    q = select(Promocao).where(Promocao.ativa.is_(True), Promocao.inicio <= hoje, Promocao.fim >= hoje)
    if unidade_id:
        q = q.where((Promocao.unidade_id.is_(None)) | (Promocao.unidade_id == unidade_id))
    return list(db.scalars(q.order_by(Promocao.id)).all())


def criar_promocao(db: Session, user: Usuario, dados: dict, ip: str | None) -> Promocao:
    exigir_perfil(user, P.GERENTE, P.ADMIN)
    if user.perfil == P.GERENTE:
        if dados.get("unidade_id") != user.unidade_id:
            raise AcessoNegado("Gerente só cadastra promoções para a própria unidade.")
    elif dados.get("unidade_id") is not None:
        obter_unidade(db, dados["unidade_id"], somente_ativa=False)
    if dados["fim"] < dados["inicio"]:
        raise ValidacaoNegocio("A data final deve ser igual ou posterior à inicial.", details=[
            {"field": "fim", "issue": "Anterior a inicio"}])
    p = Promocao(**dados)
    db.add(p)
    db.flush()
    auditoria.registrar(db, user.id, "PROMOCAO_CRIADA", "promocao", p.id, {"nome": p.nome}, ip)
    db.commit()
    return p
