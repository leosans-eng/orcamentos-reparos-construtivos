"""Exceções da comunicação com a API ORC."""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, mensagem: str, status_code: int | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status_code = status_code


class ApiNaoAutenticadoError(ApiError):
    pass


class ConflitoVersaoError(ApiError):
    def __init__(self, mensagem: str, versao_atual: int | None = None):
        super().__init__(mensagem, status_code=409)
        self.versao_atual = versao_atual


class ApiIndisponivelError(ApiError):
    pass
