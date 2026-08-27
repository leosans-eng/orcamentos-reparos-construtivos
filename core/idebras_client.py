"""Cliente HTTP para o Idebras (ASP.NET WebForms)."""

from __future__ import annotations

import html as htmlmod
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests

from app_paths import env_path

URL_IDEBRAS_PADRAO = "http://andreserver:5050"
TIMEOUT = 30

MAPA_AMBIENTES_ORC = {
    "SALA": "Sala",
    "DORMITORIO 1": "Dormitório 1",
    "DORMITORIO 2": "Dormitório 2",
    "BANHEIRO": "Banheiro",
    "COZINHA": "Cozinha",
    "AREA DE SERVICO": "Área de Serviço",
    "AREA EXTERNA": "Área Externa",
    "VARANDA": "Varanda",
    "CIRCULACAO": "Circulação",
    "RESIDENCIA INTEIRA": "Residência Inteira",
}


class IdebrasError(RuntimeError):
    """Falha de comunicação ou autenticação com o Idebras."""


@dataclass(frozen=True)
class ConjuntoIdebras:
    id: str
    nome: str


@dataclass(frozen=True)
class PlantaIdebras:
    nome: str
    area_total: str
    metodo_construtivo: str
    event_target_ambientes: str


@dataclass(frozen=True)
class AmbienteIdebras:
    ambiente: str
    tipo_piso: str
    perimetro_piso: str
    area_piso: str
    tipo_revestimento: str
    area_parede: str
    area_parede_ceramica: str
    tipo_teto: str

    @property
    def comodo_orc(self) -> str | None:
        return mapear_ambiente_orc(self.ambiente)


def carregar_credenciais_idebras(caminho: Path | None = None) -> dict[str, str]:
    origem = caminho or env_path()
    valores: dict[str, str] = {}
    if origem.is_file():
        for linha in origem.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip()
    url = (
        os.environ.get("IDEBRAS_URL")
        or valores.get("IDEBRAS_URL")
        or valores.get("url_idebras")
        or URL_IDEBRAS_PADRAO
    )
    usuario = (
        os.environ.get("user_idebras")
        or os.environ.get("USER_IDEBRAS")
        or valores.get("user_idebras")
        or valores.get("USER_IDEBRAS")
        or ""
    )
    senha = (
        os.environ.get("password_idebras")
        or os.environ.get("PASSWORD_IDEBRAS")
        or valores.get("password_idebras")
        or valores.get("PASSWORD_IDEBRAS")
        or ""
    )
    return {
        "url": url.rstrip("/"),
        "usuario": usuario.strip(),
        "senha": senha,
    }


def normalizar_ambiente(texto: str) -> str:
    if texto is None:
        return ""
    texto = htmlmod.unescape(str(texto)).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).upper()


def mapear_ambiente_orc(nome_idebras: str) -> str | None:
    chave = normalizar_ambiente(nome_idebras)
    if chave in MAPA_AMBIENTES_ORC:
        return MAPA_AMBIENTES_ORC[chave]
    if chave.startswith("COZINHA/") and "AREA DE SERVICO" in chave:
        return "Cozinha"
    if chave.startswith("CIRCULACAO"):
        return "Circulação"
    return None


def parse_decimal_br(texto: str) -> float:
    valor = htmlmod.unescape(texto or "").strip()
    if not valor:
        return 0.0
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return 0.0


def formatar_decimal_br(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _campos_form(html: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for m in re.finditer(r"<input\b[^>]*>", html, re.I):
        tag = m.group(0)
        name = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
        if not name:
            continue
        tipo = re.search(r'type=["\']([^"\']+)["\']', tag, re.I)
        tipo_val = (tipo.group(1) if tipo else "text").lower()
        if tipo_val in {"submit", "button", "image", "file"}:
            continue
        value = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
        campos[name.group(1)] = htmlmod.unescape(value.group(1) if value else "")
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", html, re.I | re.S):
        attrs, body = m.group(1), m.group(2)
        name = re.search(r'name=["\']([^"\']+)["\']', attrs, re.I)
        if not name:
            continue
        selecionado = re.search(
            r'<option[^>]*selected[^>]*value=["\']([^"\']*)["\']',
            body,
            re.I,
        )
        if selecionado:
            campos[name.group(1)] = htmlmod.unescape(selecionado.group(1))
            continue
        primeiro = re.search(r'<option[^>]*value=["\']([^"\']*)["\']', body, re.I)
        campos[name.group(1)] = htmlmod.unescape(primeiro.group(1) if primeiro else "")
    return campos


def _texto_html(fragmento: str) -> str:
    texto = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragmento, flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    return htmlmod.unescape(re.sub(r"\s+", " ", texto)).strip()


def _opcoes_select(html: str, select_id: str) -> list[tuple[str, str]]:
    padrao = (
        rf'<select[^>]*(?:id|name)=["\'](?:{re.escape(select_id)}|'
        rf'ctl00\$body\${re.escape(select_id.replace("body_", ""))})["\'][^>]*>(.*?)</select>'
    )
    m = re.search(padrao, html, re.I | re.S)
    if not m:
        m = re.search(
            rf'<select[^>]*id=["\']{re.escape(select_id)}["\'][^>]*>(.*?)</select>',
            html,
            re.I | re.S,
        )
    if not m:
        return []
    opcoes = []
    for val, txt in re.findall(
        r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>',
        m.group(1),
        re.I | re.S,
    ):
        nome = _texto_html(txt)
        if not nome or nome.upper() == "SELECIONE" or val.upper() == "SELECIONE":
            continue
        opcoes.append((htmlmod.unescape(val), nome))
    return opcoes


def _linhas_tabela(html: str, table_id: str) -> list[list[str]]:
    m = re.search(
        rf'<table\b[^>]*id=["\']{re.escape(table_id)}["\'][^>]*>(.*?)</table>',
        html,
        re.I | re.S,
    )
    if not m:
        return []
    linhas = []
    for tr in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", m.group(1), re.I | re.S):
        cels = [
            _texto_html(cel)
            for cel in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr.group(1), re.I | re.S)
        ]
        if cels:
            linhas.append(cels)
    return linhas


def _event_targets_ambientes(html: str) -> list[str]:
    alvos = []
    for m in re.finditer(
        r'title=["\']Visualizar ambientes da planta\.["\'][^>]*href=["\']javascript:__doPostBack\(&#39;([^&]+)&#39;',
        html,
        re.I,
    ):
        alvos.append(htmlmod.unescape(m.group(1)))
    if alvos:
        return alvos
    for m in re.finditer(
        r"javascript:__doPostBack\('([^']+gridplanta[^']+ctl00)'",
        html,
        re.I,
    ):
        alvos.append(m.group(1))
    return alvos


class IdebrasClient:
    def __init__(self, base_url: str | None = None, usuario: str | None = None, senha: str | None = None):
        credenciais = carregar_credenciais_idebras()
        self.base_url = (base_url or credenciais["url"]).rstrip("/")
        self.usuario = usuario if usuario is not None else credenciais["usuario"]
        self.senha = senha if senha is not None else credenciais["senha"]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 ORC-AreaPrivativa",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        self.logado = False
        self._html = ""
        self.conjuntos: list[ConjuntoIdebras] = []
        self.plantas: list[PlantaIdebras] = []
        self.ambientes: list[AmbienteIdebras] = []

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path}"

    def _get(self, path: str) -> str:
        try:
            r = self.session.get(self._url(path), timeout=TIMEOUT, allow_redirects=True)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise IdebrasError(
                f"Não foi possível conectar ao Idebras em {self.base_url}."
            ) from exc
        self._html = r.text
        return self._html

    def _post(self, path: str, data: dict[str, str]) -> str:
        try:
            r = self.session.post(
                self._url(path),
                data=data,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise IdebrasError(
                f"Falha ao comunicar com o Idebras em {self.base_url}."
            ) from exc
        self._html = r.text
        return self._html

    def _ainda_login(self, html: str) -> bool:
        return "txtsenha" in html and "btnlogin" in html

    def login(self) -> None:
        if not self.usuario or not self.senha:
            raise IdebrasError(
                "Credenciais do Idebras ausentes. "
                "Informe user_idebras e password_idebras no arquivo .env."
            )
        html = self._get("/Login")
        campos = _campos_form(html)
        payload = {
            "__VIEWSTATE": campos.get("__VIEWSTATE", ""),
            "__VIEWSTATEGENERATOR": campos.get("__VIEWSTATEGENERATOR", ""),
            "__EVENTVALIDATION": campos.get("__EVENTVALIDATION", ""),
            "txtemail": self.usuario,
            "txtsenha": self.senha,
            "btnlogin": "Login",
        }
        html = self._post("/Login", payload)
        if self._ainda_login(html):
            raise IdebrasError("Não foi possível entrar no Idebras. Verifique usuário e senha.")
        self.logado = True

    def garantir_login(self) -> None:
        if not self.logado:
            self.login()

    def listar_conjuntos(self) -> list[ConjuntoIdebras]:
        self.garantir_login()
        html = self._get("/ItensParecer/PlantaImovel")
        if self._ainda_login(html):
            self.logado = False
            self.login()
            html = self._get("/ItensParecer/PlantaImovel")
        opcoes = _opcoes_select(html, "body_dropconjuntopesquisa")
        self.conjuntos = [ConjuntoIdebras(id=val, nome=nome) for val, nome in opcoes]
        return self.conjuntos

    def pesquisar_plantas(self, conjunto_id: str) -> list[PlantaIdebras]:
        self.garantir_login()
        if not self._html or "dropconjuntopesquisa" not in self._html:
            self._get("/ItensParecer/PlantaImovel")
        campos = _campos_form(self._html)
        campos["ctl00$body$dropconjuntopesquisa"] = conjunto_id
        campos["ctl00$body$btnpesquisarplanta"] = "Pesquisar"
        html = self._post("/ItensParecer/PlantaImovel", campos)
        linhas = _linhas_tabela(html, "body_gridplanta")
        alvos = _event_targets_ambientes(html)
        plantas: list[PlantaIdebras] = []
        dados = linhas[1:] if linhas else []
        for i, cols in enumerate(dados):
            nome = cols[0] if cols else f"Planta {i + 1}"
            area = cols[1] if len(cols) > 1 else ""
            metodo = cols[2] if len(cols) > 2 else ""
            alvo = alvos[i] if i < len(alvos) else ""
            plantas.append(
                PlantaIdebras(
                    nome=nome,
                    area_total=area,
                    metodo_construtivo=metodo,
                    event_target_ambientes=alvo,
                )
            )
        self.plantas = plantas
        return plantas

    def obter_ambientes(self, event_target: str) -> list[AmbienteIdebras]:
        if not event_target:
            raise IdebrasError("Esta planta não possui o atalho de visualizar ambientes.")
        campos = _campos_form(self._html)
        campos["__EVENTTARGET"] = event_target
        campos["__EVENTARGUMENT"] = ""
        html = self._post("/ItensParecer/PlantaImovel", campos)
        linhas = _linhas_tabela(html, "body_griddescricaoplanta")
        ambientes: list[AmbienteIdebras] = []
        for cols in linhas[1:]:
            if len(cols) < 8:
                continue
            ambientes.append(
                AmbienteIdebras(
                    ambiente=cols[0],
                    tipo_piso=cols[1],
                    perimetro_piso=cols[2],
                    area_piso=cols[3],
                    tipo_revestimento=cols[4],
                    area_parede=cols[5],
                    area_parede_ceramica=cols[6],
                    tipo_teto=cols[7],
                )
            )
        self.ambientes = ambientes
        return ambientes
