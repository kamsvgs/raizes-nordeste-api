"""Exceções de domínio. Cada uma mapeia para um status HTTP e um código de erro estável."""


class DomainError(Exception):
    status_code = 400
    error = "ERRO_DE_DOMINIO"

    def __init__(self, message: str, error: str | None = None, details: list | None = None):
        super().__init__(message)
        self.message = message
        if error:
            self.error = error
        self.details = details or []


class NaoAutenticado(DomainError):
    status_code = 401
    error = "NAO_AUTENTICADO"


class CredenciaisInvalidas(NaoAutenticado):
    error = "CREDENCIAIS_INVALIDAS"


class AcessoNegado(DomainError):
    status_code = 403
    error = "ACESSO_NEGADO"


class NaoEncontrado(DomainError):
    status_code = 404
    error = "NAO_ENCONTRADO"


class Conflito(DomainError):
    status_code = 409
    error = "CONFLITO"


class ValidacaoNegocio(DomainError):
    status_code = 422
    error = "VALIDATION_ERROR"


class PagamentoRecusado(DomainError):
    status_code = 402
    error = "PAGAMENTO_RECUSADO"


class GatewayIndisponivel(DomainError):
    status_code = 503
    error = "GATEWAY_INDISPONIVEL"
