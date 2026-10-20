"""Ponto de entrada da API Raízes do Nordeste."""
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from app.api.errors import registrar_handlers
from app.api.openapi_docs import instalar as instalar_openapi
from app.api.routers import auditoria, auth, catalogo, estoque, fidelidade, pedidos

DESCRICAO = """
API back-end da rede **Raízes do Nordeste** – Projeto Multidisciplinar (trilha Back-End).

**Como testar no Swagger:** faça `POST /auth/login` com um usuário do seed (ver README), copie o `accessToken`
e clique em **Authorize**. Tokens do pagamento mock: `tok_aprovado`, `tok_recusado`, `tok_timeout`.
"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
acesso = logging.getLogger("raizes.acesso")

app = FastAPI(title="Raízes do Nordeste – API", version="1.0.0", description=DESCRICAO)
registrar_handlers(app)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    inicio = time.perf_counter()
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = request.state.request_id
    acesso.info("requestId=%s %s %s -> %s (%.0f ms)", request.state.request_id, request.method, request.url.path,
                resp.status_code, (time.perf_counter() - inicio) * 1000)
    return resp


for r in (auth.router, catalogo.router, estoque.router, pedidos.router, fidelidade.router, auditoria.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def painel():
    """Painel simples de testes manuais (a documentação oficial da API é o Swagger, em /docs)."""
    return FileResponse(Path(__file__).parent / "static" / "painel.html", media_type="text/html")


instalar_openapi(app)
