from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db, ip_origem
from app.application import catalogo
from app.infrastructure.db.models import Usuario

router = APIRouter(tags=["Catálogo"])
PAGE = Query(1, ge=1)
LIMIT = Query(10, ge=1, le=100, description="Máximo de 100 itens por página")


@router.get("/unidades", response_model=s.Page[s.UnidadeOut], summary="Listar unidades ativas")
def listar_unidades(page: int = PAGE, limit: int = LIMIT, db: Session = Depends(get_db)):
    itens, total = catalogo.listar_unidades(db, page, limit)
    return s.Page(items=itens, page=page, limit=limit, total=total)


@router.get("/unidades/{unidade_id}", response_model=s.UnidadeOut, summary="Consultar unidade")
def obter_unidade(unidade_id: int, db: Session = Depends(get_db)):
    return catalogo.obter_unidade(db, unidade_id)


@router.post("/unidades", response_model=s.UnidadeOut, status_code=201, summary="Cadastrar unidade (ADMIN)")
def criar_unidade(body: s.UnidadeIn, request: Request, user: Usuario = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return catalogo.criar_unidade(db, user, body.model_dump(), ip_origem(request))


@router.patch("/unidades/{unidade_id}", response_model=s.UnidadeOut, summary="Atualizar unidade (ADMIN)")
def atualizar_unidade(unidade_id: int, body: s.UnidadePatch, request: Request,
                      user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return catalogo.atualizar_unidade(db, user, unidade_id, body.model_dump(exclude_unset=True, exclude_none=True),
                                      ip_origem(request))


@router.get("/produtos", response_model=s.Page[s.ProdutoOut], summary="Listar produtos (paginado)")
def listar_produtos(page: int = PAGE, limit: int = LIMIT, categoria: str | None = None, db: Session = Depends(get_db)):
    itens, total = catalogo.listar_produtos(db, page, limit, categoria)
    return s.Page(items=itens, page=page, limit=limit, total=total)


@router.get("/produtos/{produto_id}", response_model=s.ProdutoOut, summary="Consultar produto")
def obter_produto(produto_id: int, db: Session = Depends(get_db)):
    return catalogo.obter_produto(db, produto_id)


@router.post("/produtos", response_model=s.ProdutoOut, status_code=201, summary="Cadastrar produto (ADMIN)")
def criar_produto(body: s.ProdutoIn, request: Request, user: Usuario = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return catalogo.criar_produto(db, user, body.model_dump(), ip_origem(request))


@router.put("/produtos/{produto_id}", response_model=s.ProdutoOut, summary="Atualizar produto (ADMIN)")
def atualizar_produto(produto_id: int, body: s.ProdutoIn, request: Request, user: Usuario = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    return catalogo.atualizar_produto(db, user, produto_id, body.model_dump(), ip_origem(request))


@router.delete("/produtos/{produto_id}", status_code=204, summary="Inativar produto (ADMIN)")
def inativar_produto(produto_id: int, request: Request, user: Usuario = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    catalogo.inativar_produto(db, user, produto_id, ip_origem(request))
    return Response(status_code=204)


@router.get("/unidades/{unidade_id}/cardapio", response_model=s.Page[s.CardapioItemOut],
            summary="Cardápio da unidade (itens disponíveis)")
def cardapio(unidade_id: int, page: int = PAGE, limit: int = LIMIT, categoria: str | None = None,
             db: Session = Depends(get_db)):
    rows, total = catalogo.cardapio(db, unidade_id, page, limit, categoria)
    itens = [s.CardapioItemOut(produto_id=p.id, nome=p.nome, descricao=p.descricao, categoria=p.categoria,
                               preco=c.preco_unidade if c.preco_unidade is not None else p.preco_base,
                               sazonal=p.sazonal) for c, p in rows]
    return s.Page(items=itens, page=page, limit=limit, total=total)


@router.put("/unidades/{unidade_id}/cardapio/{produto_id}", response_model=s.CardapioConfigOut,
            summary="Definir disponibilidade e preço local (GERENTE/ADMIN)")
def definir_cardapio(unidade_id: int, produto_id: int, body: s.CardapioItemIn, request: Request,
                     user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return catalogo.definir_item_cardapio(db, user, unidade_id, produto_id, body.disponivel, body.preco_unidade,
                                          ip_origem(request))


@router.get("/promocoes", response_model=list[s.PromocaoOut], summary="Promoções vigentes")
def listar_promocoes(unidade_id: int | None = Query(None, alias="unidadeId"), db: Session = Depends(get_db)):
    return catalogo.promocoes_vigentes(db, unidade_id)


@router.post("/promocoes", response_model=s.PromocaoOut, status_code=201, summary="Cadastrar promoção (GERENTE/ADMIN)")
def criar_promocao(body: s.PromocaoIn, request: Request, user: Usuario = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return catalogo.criar_promocao(db, user, body.model_dump(), ip_origem(request))
