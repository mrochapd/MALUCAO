"""Guarda o usuário e o IP da requisição atual para o registro de auditoria."""
from contextvars import ContextVar

_requisicao_atual: ContextVar = ContextVar("requisicao_atual", default=None)


def requisicao_atual():
    return _requisicao_atual.get()


class UsuarioAtualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _requisicao_atual.set(request)
        try:
            return self.get_response(request)
        finally:
            _requisicao_atual.reset(token)
