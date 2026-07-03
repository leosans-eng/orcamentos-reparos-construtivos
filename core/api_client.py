"""Cliente HTTP para a API ORC."""

from __future__ import annotations

from typing import Any

import requests

from core.api_config import carregar_config, carregar_sessao, limpar_sessao, salvar_sessao
from core.api_exceptions import (
    ApiError,
    ApiIndisponivelError,
    ApiNaoAutenticadoError,
    ConflitoVersaoError,
)

_cliente: "OrcApiClient | None" = None


class OrcApiClient:
    def __init__(self, base_url: str, access_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.username: str | None = None
        sessao = carregar_sessao()
        if sessao and access_token is None:
            self.access_token = sessao.get("access_token")
            self.username = sessao.get("username")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            response = requests.request(
                method,
                self._url(path),
                headers=self._headers(),
                timeout=kwargs.pop("timeout", 30),
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiIndisponivelError(
                f"Não foi possível conectar à API em {self.base_url}.\n"
                "Verifique se o servidor está em execução e a URL nas configurações."
            ) from exc
        return response

    def _mensagem_erro(self, response: requests.Response, padrao: str) -> str:
        try:
            corpo = response.json()
            if isinstance(corpo, dict) and corpo.get("detail") is not None:
                detalhe = corpo["detail"]
                if isinstance(detalhe, str):
                    return detalhe
                if isinstance(detalhe, dict) and detalhe.get("mensagem"):
                    return str(detalhe["mensagem"])
        except ValueError:
            pass
        return padrao

    def _tratar_resposta(self, response: requests.Response) -> Any:
        if response.status_code == 401:
            raise ApiNaoAutenticadoError(
                self._mensagem_erro(response, "Sessão expirada. Faça login novamente."),
                401,
            )
        if response.status_code == 403:
            raise ApiError(
                self._mensagem_erro(response, "Acesso negado."),
                403,
            )
        if response.status_code == 409:
            try:
                detalhe = response.json()
            except ValueError:
                detalhe = {"mensagem": response.text}
            if isinstance(detalhe, dict) and detalhe.get("detail") == "conflito_versao":
                payload = detalhe
            elif isinstance(detalhe.get("detail"), dict):
                payload = detalhe["detail"]
            else:
                payload = detalhe
            raise ConflitoVersaoError(
                str(payload.get("mensagem", "Conflito de versão. Recarregue os dados.")),
                versao_atual=payload.get("versao_atual"),
            )
        if response.status_code >= 400:
            raise ApiError(
                self._mensagem_erro(response, response.text or "Erro na API."),
                response.status_code,
            )
        if response.status_code == 204:
            return None
        if not response.content:
            return None
        return response.json()

    def health(self) -> bool:
        try:
            response = self._request("GET", "/api/health")
            return response.status_code == 200
        except ApiError:
            return False

    def login(self, username: str, password: str) -> str:
        response = self._request(
            "POST",
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        dados = self._tratar_resposta(response)
        token = dados["access_token"]
        self.access_token = token
        self.username = dados.get("username", username)
        salvar_sessao(token, self.username or username)
        return token

    def logout(self) -> None:
        self.access_token = None
        self.username = None
        limpar_sessao()

    def trocar_senha(self, senha_atual: str, senha_nova: str) -> dict:
        response = self._request(
            "POST",
            "/api/auth/change-password",
            json={"senha_atual": senha_atual, "senha_nova": senha_nova},
        )
        return self._tratar_resposta(response)

    def listar_usuarios(self) -> list:
        response = self._request("GET", "/api/auth/users")
        return self._tratar_resposta(response)

    def get_composicoes_catalogo(self) -> dict:
        response = self._request("GET", "/api/composicoes/catalogo")
        return self._tratar_resposta(response)

    def salvar_estado_previa_custos(self, estado: str) -> dict:
        response = self._request(
            "PATCH",
            "/api/composicoes/catalogo/estado-previa",
            json={"estado": estado},
        )
        return self._tratar_resposta(response)

    def criar_composicao(self, codigo: str, nome: str, unidade: str, componentes=None) -> dict:
        payload = {
            "codigo": codigo,
            "nome": nome,
            "unidade": unidade,
            "componentes": componentes,
        }
        response = self._request("POST", "/api/composicoes", json=payload)
        return self._tratar_resposta(response)

    def atualizar_composicao(self, composicao_id: str, composicao: dict, versao: int) -> dict:
        response = self._request(
            "PUT",
            f"/api/composicoes/{composicao_id}",
            json={"composicao": composicao, "versao": versao},
        )
        return self._tratar_resposta(response)

    def excluir_composicao(self, composicao_id: str) -> None:
        response = self._request("DELETE", f"/api/composicoes/{composicao_id}")
        self._tratar_resposta(response)

    def get_etapas_catalogo(self) -> dict:
        response = self._request("GET", "/api/etapas/catalogo")
        return self._tratar_resposta(response)

    def criar_etapa(self, nome: str) -> dict:
        response = self._request("POST", "/api/etapas", json={"nome": nome})
        return self._tratar_resposta(response)

    def atualizar_etapa(self, etapa_id: str, etapa: dict, versao: int) -> dict:
        response = self._request(
            "PUT",
            f"/api/etapas/{etapa_id}",
            json={"etapa": etapa, "versao": versao},
        )
        return self._tratar_resposta(response)

    def excluir_etapa(self, etapa_id: str) -> None:
        response = self._request("DELETE", f"/api/etapas/{etapa_id}")
        self._tratar_resposta(response)


def get_client() -> OrcApiClient:
    global _cliente
    if _cliente is None:
        config = carregar_config()
        _cliente = OrcApiClient(config["base_url"])
    return _cliente


def reiniciar_cliente(base_url: str | None = None, access_token: str | None = None) -> OrcApiClient:
    global _cliente
    config = carregar_config()
    url = (base_url or config["base_url"]).rstrip("/")
    _cliente = OrcApiClient(url, access_token=access_token)
    return _cliente
