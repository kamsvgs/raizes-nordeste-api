"""Tratamento padronizado de erros (RNF12): todo erro retorna o mesmo JSON."""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import DomainError

log = logging.getLogger("raizes")


def corpo(request: Request, error: str, message: str, details: list | None = None) -> dict:
    return {
        "error": error,
        "message": message,
        "details": details or [],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "path": request.url.path,
        "requestId": getattr(request.state, "request_id", str(uuid.uuid4())),
    }


def _campo(loc) -> str:
    partes = [p for p in loc if p not in ("body", "query", "path")]
    s = ""
    for p in partes:
        s += f"[{p}]" if isinstance(p, int) else (f".{p}" if s else str(p))
    return s or "corpo"


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _dominio(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status_code, content=corpo(request, exc.error, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError):
        erros = exc.errors()
        if any(e["type"] == "json_invalid" for e in erros):
            return JSONResponse(status_code=400, content=corpo(request, "REQUISICAO_INVALIDA", "JSON malformado."))
        detalhes = []
        for e in erros:
            if e["type"] == "missing":
                issue = "Campo obrigatório"
            elif e["type"] in ("enum", "literal_error"):
                issue = f"Valor inválido. Valores aceitos: {e.get('ctx', {}).get('expected', '')}".replace("'", "")
            else:
                issue = e["msg"].removeprefix("Value error, ")
            detalhes.append({"field": _campo(e["loc"]), "issue": issue})
        return JSONResponse(status_code=422, content=corpo(request, "VALIDATION_ERROR", "Dados inválidos.", detalhes))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        nomes = {404: "ROTA_NAO_ENCONTRADA", 405: "METODO_NAO_PERMITIDO"}
        return JSONResponse(status_code=exc.status_code,
                            content=corpo(request, nomes.get(exc.status_code, "ERRO_HTTP"), str(exc.detail)))

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        log.exception("Erro inesperado")
        return JSONResponse(status_code=500, content=corpo(request, "ERRO_INTERNO", "Erro interno do servidor."))
