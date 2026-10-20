"""Funções compartilhadas pelos casos de uso (visibilidade e escopo por perfil – RN15)."""
from sqlalchemy.orm import Session

from app.domain.enums import PerfilUsuario
from app.domain.exceptions import AcessoNegado, NaoEncontrado
from app.infrastructure.db.models import Cliente, Pedido, Usuario
from app.infrastructure.db.repositorios import ClienteRepo


def cliente_do_usuario(db: Session, user: Usuario) -> Cliente | None:
    return ClienteRepo(db).do_usuario(user)


def exigir_perfil(user: Usuario, *perfis: PerfilUsuario) -> None:
    if user.perfil not in perfis:
        raise AcessoNegado("Seu perfil não tem permissão para esta operação.")


def exigir_unidade(user: Usuario, unidade_id: int) -> None:
    """RN15: gerente/atendente/cozinha só atuam na própria unidade; ADMIN em todas."""
    if user.perfil != PerfilUsuario.ADMIN and user.unidade_id != unidade_id:
        raise AcessoNegado("Operação permitida apenas para a unidade a que você está vinculado.")


def pedido_visivel(db: Session, user: Usuario, pedido: Pedido) -> bool:
    if user.perfil == PerfilUsuario.ADMIN:
        return True
    if user.perfil == PerfilUsuario.CLIENTE:
        c = cliente_do_usuario(db, user)
        return bool(c and pedido.cliente_id == c.id)
    return pedido.unidade_id == user.unidade_id


def pedido_ou_404(db: Session, user: Usuario, pedido: Pedido | None) -> Pedido:
    if pedido is None or not pedido_visivel(db, user, pedido):
        raise NaoEncontrado("Pedido não encontrado.", "PEDIDO_NAO_ENCONTRADO")
    return pedido
