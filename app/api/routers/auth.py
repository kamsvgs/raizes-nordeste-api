from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api import schemas as s
from app.api.deps import get_current_user, get_db, ip_origem
from app.application import contas
from app.infrastructure.db.models import Usuario

router = APIRouter(tags=["Auth e contas"])


@router.post("/auth/register", response_model=s.UsuarioOut, status_code=201, summary="Cadastro de cliente")
def register(body: s.RegistroIn, request: Request, db: Session = Depends(get_db)):
    return contas.registrar_cliente(db, body.nome, body.email, body.senha, body.telefone, body.data_nascimento,
                                    ip_origem(request))


@router.post("/auth/login", response_model=s.TokenOut, summary="Login (retorna token JWT)")
def login(body: s.LoginIn, request: Request, db: Session = Depends(get_db)):
    u, token, expira = contas.autenticar(db, body.email, body.senha, ip_origem(request))
    return s.TokenOut(access_token=token, expires_in=expira, user=s.UsuarioOut.model_validate(u))


@router.get("/auth/me", response_model=s.UsuarioOut, summary="Dados do usuário logado")
def me(user: Usuario = Depends(get_current_user)):
    return user


@router.post("/usuarios", response_model=s.UsuarioOut, status_code=201, summary="Cadastrar funcionário (ADMIN)")
def criar_usuario(body: s.UsuarioInternoIn, request: Request, user: Usuario = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return contas.criar_usuario_interno(db, user, body.nome, body.email, body.senha, body.perfil, body.unidade_id,
                                        ip_origem(request))


@router.get("/clientes/me", response_model=s.ClienteOut, summary="Consultar os próprios dados (direito de acesso)")
def cliente_me(request: Request, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    c = contas.consultar_dados_pessoais(db, user, ip_origem(request))
    return s.ClienteOut(id=c.id, nome=user.nome, email=user.email, telefone=c.telefone,
                        data_nascimento=c.data_nascimento)


@router.delete("/clientes/me", status_code=204, summary="Solicitar anonimização (direito de eliminação)")
def anonimizar(request: Request, user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    contas.anonimizar_cliente(db, user, ip_origem(request))
    return Response(status_code=204)
