"""Enriquece o OpenAPI com os códigos de status e o padrão de erro de cada endpoint.

Regras: toda operação protegida documenta 401; operações com corpo documentam 400 e 422; os demais códigos
(402, 403, 404, 409, 503) vêm da tabela abaixo, com o nome de erro (campo `error`) real de cada caso.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

DESCRICAO = {
    400: "Requisição malformada (ex.: JSON inválido)", 401: "Não autenticado (token ausente, inválido ou expirado)",
    402: "Pagamento recusado pelo gateway", 403: "Perfil sem permissão para a operação/unidade",
    404: "Recurso não encontrado", 409: "Conflito com regra de negócio ou estado atual",
    422: "Falha de validação de campos", 503: "Gateway de pagamento indisponível",
}
NOMES = {400: "REQUISICAO_INVALIDA", 401: "NAO_AUTENTICADO", 402: "PAGAMENTO_RECUSADO", 403: "ACESSO_NEGADO",
         404: "NAO_ENCONTRADO", 409: "CONFLITO", 422: "VALIDATION_ERROR", 503: "GATEWAY_INDISPONIVEL"}

# (método, rota) -> [(status, nome do erro)]
EXTRAS: dict[tuple[str, str], list[tuple[int, str | None]]] = {
    ("post", "/auth/register"): [(409, "EMAIL_JA_CADASTRADO")],
    ("post", "/auth/login"): [(401, "CREDENCIAIS_INVALIDAS")],
    ("post", "/usuarios"): [(403, None), (404, "UNIDADE_NAO_ENCONTRADA"), (409, "EMAIL_JA_CADASTRADO")],
    ("get", "/clientes/me"): [(403, None)], ("delete", "/clientes/me"): [(403, None)],
    ("get", "/unidades/{unidade_id}"): [(404, "UNIDADE_NAO_ENCONTRADA")],
    ("post", "/unidades"): [(403, None)], ("patch", "/unidades/{unidade_id}"): [(403, None), (404, "UNIDADE_NAO_ENCONTRADA")],
    ("get", "/produtos/{produto_id}"): [(404, "PRODUTO_NAO_ENCONTRADO")],
    ("post", "/produtos"): [(403, None)],
    ("put", "/produtos/{produto_id}"): [(403, None), (404, "PRODUTO_NAO_ENCONTRADO")],
    ("delete", "/produtos/{produto_id}"): [(403, None), (404, "PRODUTO_NAO_ENCONTRADO")],
    ("get", "/unidades/{unidade_id}/cardapio"): [(404, "UNIDADE_NAO_ENCONTRADA")],
    ("put", "/unidades/{unidade_id}/cardapio/{produto_id}"): [(403, None), (404, "UNIDADE_NAO_ENCONTRADA")],
    ("post", "/promocoes"): [(403, None)],
    ("get", "/unidades/{unidade_id}/estoque"): [(403, None), (404, "UNIDADE_NAO_ENCONTRADA")],
    ("post", "/estoque/movimentos"): [(403, None), (404, "PRODUTO_NAO_ENCONTRADO"), (409, "ESTOQUE_INSUFICIENTE")],
    ("post", "/pedidos"): [(403, None), (404, "PRODUTO_NAO_ENCONTRADO"), (409, "ESTOQUE_INSUFICIENTE")],
    ("get", "/pedidos/{pedido_id}"): [(404, "PEDIDO_NAO_ENCONTRADO")],
    ("patch", "/pedidos/{pedido_id}/status"): [(403, None), (404, "PEDIDO_NAO_ENCONTRADO"), (409, "TRANSICAO_INVALIDA")],
    ("post", "/pedidos/{pedido_id}/cancelamento"): [(403, None), (404, "PEDIDO_NAO_ENCONTRADO"), (409, "TRANSICAO_INVALIDA")],
    ("post", "/pedidos/{pedido_id}/pagamento"): [(402, None), (403, None), (404, "PEDIDO_NAO_ENCONTRADO"),
                                                  (409, "PEDIDO_NAO_AGUARDA_PAGAMENTO"), (503, None)],
    ("get", "/pedidos/{pedido_id}/pagamento"): [(404, "PAGAMENTO_NAO_ENCONTRADO")],
    ("post", "/fidelidade/consentimentos"): [(403, None)], ("get", "/fidelidade/consentimentos"): [(403, None)],
    ("get", "/fidelidade/saldo"): [(403, None)], ("get", "/fidelidade/historico"): [(403, None)],
    ("get", "/auditoria"): [(403, None)],
}

_SCHEMA_ERRO = {
    "type": "object",
    "properties": {
        "error": {"type": "string"}, "message": {"type": "string"},
        "details": {"type": "array", "items": {"type": "object", "properties": {
            "field": {"type": "string"}, "issue": {"type": "string"}}}},
        "timestamp": {"type": "string", "format": "date-time"}, "path": {"type": "string"},
        "requestId": {"type": "string"},
    },
    "required": ["error", "message", "details", "timestamp", "path", "requestId"],
}


def _resposta(codigo: int, nome: str | None, path: str) -> dict:
    nome = nome or NOMES[codigo]
    detalhes = [{"field": "canalPedido", "issue": "Campo obrigatório"}] if codigo == 422 else []
    return {"description": DESCRICAO[codigo], "content": {"application/json": {
        "schema": _SCHEMA_ERRO,
        "example": {"error": nome, "message": DESCRICAO[codigo] + ".", "details": detalhes,
                    "timestamp": "2026-10-16T12:00:00Z", "path": path,
                    "requestId": "b3f1c2d4-8a7e-4c11-9d0a-5e6f7a8b9c01"}}}}


def instalar(app: FastAPI) -> None:
    def custom():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        for path, ops in schema["paths"].items():
            for metodo, op in ops.items():
                resp = op.setdefault("responses", {})
                codigos: dict[int, str | None] = {}
                if "security" in op:
                    codigos[401] = None
                if "requestBody" in op:
                    codigos[400] = None
                for cod, nome in EXTRAS.get((metodo, path), []):
                    codigos[cod] = nome
                resp.pop("422", None)
                if "requestBody" in op or op.get("parameters"):
                    codigos[422] = None
                for cod, nome in sorted(codigos.items()):
                    resp[str(cod)] = _resposta(cod, nome, path)
                if (metodo, path) == ("post", "/pedidos"):
                    resp["200"] = {"description": "Repetição com a mesma Idempotency-Key: devolve o pedido original (RN14)",
                                   "content": resp["201"]["content"]}
        app.openapi_schema = schema
        return schema

    app.openapi = custom
