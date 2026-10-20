"""Carga de dados de exemplo (desenvolvimento e avaliação). Idempotente: não duplica se já houver unidades.

Uso:  python -m app.infrastructure.db.seed
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import FinalidadeDados, PerfilUsuario as P
from app.infrastructure.db.models import (CardapioUnidade, Cliente, Consentimento, Estoque, Produto, Unidade, Usuario)
from app.infrastructure.security import hash_senha

SENHA = "Senha@123"


def seed(db: Session) -> bool:
    if db.scalar(select(Unidade.id).limit(1)) is not None:
        return False
    db.add_all([
        Unidade(id=1, nome="Raízes Boa Viagem", cidade="Recife", uf="PE", cozinha_completa=True),
        Unidade(id=2, nome="Raízes Aldeota", cidade="Fortaleza", uf="CE", cozinha_completa=False),
    ])
    produtos = [
        (10, "Tapioca de queijo coalho", "Tapioca recheada com queijo coalho", "Tapiocas", "12.50", False),
        (11, "Cuscuz recheado", "Cuscuz com carne de sol", "Cuscuz", "15.00", False),
        (12, "Bolo de macaxeira", "Fatia de bolo de macaxeira", "Doces", "9.00", False),
        (13, "Suco de cajá", "Suco natural 400 ml", "Bebidas", "8.00", False),
        (14, "Café da manhã completo", "Cuscuz, ovo, queijo, pão e café", "Combos", "24.90", False),
        (15, "Bolo de rolo (sazonal)", "Edição junina", "Doces", "11.00", True),
    ]
    db.add_all([Produto(id=i, nome=n, descricao=d, categoria=c, preco_base=Decimal(p), sazonal=s)
                for i, n, d, c, p, s in produtos])
    db.flush()
    # cardápio e estoque por unidade (a unidade 2 tem cozinha reduzida)
    for pid in (10, 11, 12, 13, 14, 15):
        db.add(CardapioUnidade(unidade_id=1, produto_id=pid, disponivel=True))
        db.add(Estoque(unidade_id=1, produto_id=pid, quantidade={10: 100, 11: 80, 12: 50, 13: 100, 14: 40, 15: 30}[pid]))
    for pid in (10, 11, 13):
        db.add(CardapioUnidade(unidade_id=2, produto_id=pid, disponivel=True))
        db.add(Estoque(unidade_id=2, produto_id=pid, quantidade={10: 60, 11: 40, 13: 60}[pid]))
    db.add(CardapioUnidade(unidade_id=2, produto_id=15, disponivel=False))

    h = hash_senha(SENHA)
    funcionarios = [("Administrador", "admin@raizes.test", P.ADMIN, None),
                    ("Gerente Recife", "gerente.recife@raizes.test", P.GERENTE, 1),
                    ("Atendente Recife", "atendente.recife@raizes.test", P.ATENDENTE, 1),
                    ("Cozinha Recife", "cozinha.recife@raizes.test", P.COZINHA, 1)]
    for nome, email, perfil, uid in funcionarios:
        db.add(Usuario(nome=nome, email=email, senha_hash=h, perfil=perfil, unidade_id=uid))
    for nome, email, consente in (("Cliente Exemplo", "cliente@raizes.test", True),
                                  ("Cliente Dois", "cliente2@raizes.test", False)):
        u = Usuario(nome=nome, email=email, senha_hash=h, perfil=P.CLIENTE)
        db.add(u)
        db.flush()
        c = Cliente(usuario_id=u.id)
        db.add(c)
        db.flush()
        if consente:
            db.add(Consentimento(cliente_id=c.id, finalidade=FinalidadeDados.FIDELIDADE, concedido=True,
                                 versao_termo="2026-01"))
    db.commit()
    return True


if __name__ == "__main__":
    from app.infrastructure.db.base import SessionLocal

    with SessionLocal() as s:
        print("Seed aplicado." if seed(s) else "Banco já possui dados; nada a fazer.")
