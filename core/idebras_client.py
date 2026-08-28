"""Cliente HTTP para o Idebras (ASP.NET WebForms)."""

from __future__ import annotations

import html as htmlmod
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests

from app_paths import env_paths, is_frozen
from core.idebras_secrets import (
    carregar_credenciais_empacotadas,
    usar_apenas_credenciais_empacotadas,
)

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


@dataclass(frozen=True)
class ParecerFinalizado:
    nome: str
    id_mutuario: str
    cpf: str
    conjunto: str
    conjunto_id: str
    endereco: str
    bloco: str
    apartamento: str
    cidade: str
    uf: str
    data: str

    @property
    def cidade_uf(self) -> str:
        if self.cidade and self.uf:
            return f"{self.cidade}/{self.uf}"
        return self.cidade or self.uf or ""


@dataclass(frozen=True)
class ResultadoPesquisaPareceres:
    pareceres: list[ParecerFinalizado]
    total: int


def _ler_arquivo_env(origem: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if origem is None or not origem.is_file():
        return valores
    for linha in origem.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip()
    return valores


def _credenciais_de_valores(valores: dict[str, str], *, usar_environ: bool) -> dict[str, str]:
    url = valores.get("IDEBRAS_URL") or valores.get("url_idebras") or ""
    usuario = valores.get("user_idebras") or valores.get("USER_IDEBRAS") or ""
    senha = valores.get("password_idebras") or valores.get("PASSWORD_IDEBRAS") or ""
    if usar_environ:
        url = os.environ.get("IDEBRAS_URL") or url
        usuario = (
            os.environ.get("user_idebras")
            or os.environ.get("USER_IDEBRAS")
            or usuario
        )
        senha = (
            os.environ.get("password_idebras")
            or os.environ.get("PASSWORD_IDEBRAS")
            or senha
        )
    return {
        "url": (url or URL_IDEBRAS_PADRAO).rstrip("/"),
        "usuario": usuario.strip(),
        "senha": senha,
    }


def carregar_credenciais_idebras(caminho: Path | None = None) -> dict[str, str]:
    if caminho is not None:
        return _credenciais_de_valores(_ler_arquivo_env(caminho), usar_environ=False)

    empacotadas = carregar_credenciais_empacotadas() or {}
    if usar_apenas_credenciais_empacotadas():
        return {
            "url": (empacotadas.get("url") or URL_IDEBRAS_PADRAO).rstrip("/"),
            "usuario": (empacotadas.get("usuario") or "").strip(),
            "senha": empacotadas.get("senha") or "",
        }

    valores: dict[str, str] = {}
    for origem in env_paths():
        valores = _ler_arquivo_env(origem)
        if valores:
            break
    lidas = _credenciais_de_valores(valores, usar_environ=True)
    if not lidas["usuario"] and empacotadas.get("usuario"):
        lidas["usuario"] = empacotadas["usuario"].strip()
    if not lidas["senha"] and empacotadas.get("senha"):
        lidas["senha"] = empacotadas["senha"]
    if lidas["url"] == URL_IDEBRAS_PADRAO and empacotadas.get("url"):
        lidas["url"] = empacotadas["url"].rstrip("/")
    return lidas


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


def medidas_para_orcamento(ambientes: list[AmbienteIdebras]) -> dict[str, dict[str, float]]:
    medidas: dict[str, dict[str, float]] = {}
    for amb in ambientes:
        destino = amb.comodo_orc
        if not destino:
            continue
        medidas[destino] = {
            "piso": parse_decimal_br(amb.area_piso),
            "rev_arg": parse_decimal_br(amb.area_parede),
            "rev_cer": parse_decimal_br(amb.area_parede_ceramica),
        }
    return medidas


def _nome_conjunto_sem_prefixo(nome: str) -> str:
    texto = re.sub(r"\s*\(\d+\)\s*$", "", nome or "").strip()
    if " - " in texto:
        return texto.split(" - ", 1)[1].strip()
    return texto


def localizar_conjunto_parecer(
    conjuntos: list[ConjuntoIdebras],
    parecer: ParecerFinalizado,
) -> ConjuntoIdebras | None:
    if parecer.conjunto_id:
        for conjunto in conjuntos:
            if conjunto.id != parecer.conjunto_id:
                continue
            alvo_id = normalizar_ambiente(parecer.conjunto)
            if not alvo_id or alvo_id in normalizar_ambiente(conjunto.nome):
                return conjunto
            break
    alvo = normalizar_ambiente(parecer.conjunto)
    cidade = normalizar_ambiente(parecer.cidade)
    if not alvo:
        return None
    exatos: list[ConjuntoIdebras] = []
    parciais: list[ConjuntoIdebras] = []
    for conjunto in conjuntos:
        nome_todo = normalizar_ambiente(conjunto.nome)
        nome_limpo = normalizar_ambiente(_nome_conjunto_sem_prefixo(conjunto.nome))
        if nome_limpo == alvo:
            exatos.append(conjunto)
        elif alvo in nome_todo:
            parciais.append(conjunto)
    return _escolher_conjunto_por_cidade(exatos, cidade) or _escolher_conjunto_por_cidade(
        parciais, cidade
    )


def _escolher_conjunto_por_cidade(
    candidatos: list[ConjuntoIdebras],
    cidade: str = "",
) -> ConjuntoIdebras | None:
    if not candidatos:
        return None
    if cidade:
        com_cidade = [
            c for c in candidatos if cidade in normalizar_ambiente(c.nome)
        ]
        if len(com_cidade) == 1:
            return com_cidade[0]
        if len(com_cidade) > 1:
            return com_cidade[0]
    if len(candidatos) == 1:
        return candidatos[0]
    if not cidade and len(candidatos) > 1:
        return None
    return candidatos[0] if candidatos else None


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
    linhas = []
    for cels in _celulas_html_tabela(html, table_id):
        linhas.append([_texto_html(cel) for cel in cels])
    return linhas


def _celulas_html_tabela(html: str, table_id: str) -> list[list[str]]:
    m = re.search(
        rf'<table\b[^>]*id=["\']{re.escape(table_id)}["\'][^>]*>(.*?)</table>',
        html,
        re.I | re.S,
    )
    if not m:
        return []
    linhas = []
    for tr in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", m.group(1), re.I | re.S):
        cels = re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr.group(1), re.I | re.S)
        if cels:
            linhas.append(cels)
    return linhas


def _texto_com_linhas(fragmento: str) -> list[str]:
    texto = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragmento, flags=re.I | re.S)
    texto = re.sub(r"</?br\s*/?>", "\n", texto, flags=re.I)
    texto = re.sub(r"</p>", "\n", texto, flags=re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    linhas = []
    for ln in texto.splitlines():
        ln = htmlmod.unescape(re.sub(r"[ \t]+", " ", ln)).strip()
        if ln:
            linhas.append(ln)
    return linhas


_RE_CODIGO_INTERNO = re.compile(r"^\d+\.[A-Z0-9.]+", re.I)


def _parse_celula_mutuario(html_celula: str) -> dict[str, str]:
    linhas = _texto_com_linhas(html_celula)
    dados = {
        "nome": "",
        "id_mutuario": "",
        "cpf": "",
        "conjunto": "",
        "endereco": "",
        "bloco": "",
        "apartamento": "",
        "cidade": "",
        "uf": "",
    }
    if not linhas:
        return dados
    cabeca = re.match(r"^(.*?)\s*\((\d+)\)\s*$", linhas[0])
    if cabeca:
        dados["nome"] = cabeca.group(1).strip()
        dados["id_mutuario"] = cabeca.group(2)
    else:
        dados["nome"] = linhas[0]
    for ln in linhas[1:]:
        compacto = ln.replace(" ", "")
        if _RE_CODIGO_INTERNO.match(compacto):
            continue
        low = ln.lower()
        if low.startswith("cpf"):
            dados["cpf"] = re.sub(r"(?i)^cpf:\s*", "", ln).strip()
            continue
        if re.match(r"(?i)^endere", ln):
            dados["endereco"] = re.sub(r"(?i)^endere[cç]o:\s*", "", ln).strip()
            continue
        if "cidade/uf" in low:
            resto = re.sub(r"(?i).*cidade/uf:\s*", "", ln).strip()
            if "/" in resto:
                cidade, uf = [p.strip() for p in resto.rsplit("/", 1)]
                dados["cidade"] = cidade
                dados["uf"] = uf
            else:
                dados["cidade"] = resto
            continue
        if "bloco:" in low or "apartamento:" in low:
            bloco = re.search(r"(?i)bloco:\s*(\S*)", ln)
            apto = re.search(r"(?i)apartamento:\s*(\S*)", ln)
            if bloco:
                dados["bloco"] = bloco.group(1).strip()
            if apto:
                dados["apartamento"] = apto.group(1).strip()
            continue
        if not dados["conjunto"]:
            dados["conjunto"] = ln
    return dados


def _valor_hidden(html: str, input_id: str) -> str:
    m = re.search(
        rf'id=["\']{re.escape(input_id)}["\'][^>]*value=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if m:
        return htmlmod.unescape(m.group(1))
    m = re.search(
        rf'value=["\']([^"\']*)["\'][^>]*id=["\']{re.escape(input_id)}["\']',
        html,
        re.I,
    )
    return htmlmod.unescape(m.group(1)) if m else ""


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
            if is_frozen():
                raise IdebrasError(
                    "Credenciais do Idebras ausentes no pacote. "
                    "Gere o instalador com o arquivo .env na máquina de build."
                )
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
        if not self._html or "btnpesquisarplanta" not in self._html:
            self._get("/ItensParecer/PlantaImovel")
            if self._ainda_login(self._html):
                self.logado = False
                self.login()
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

    def pesquisar_pareceres_finalizados(
        self,
        nome_cliente: str = "",
        conjunto_id: str = "",
    ) -> ResultadoPesquisaPareceres:
        self.garantir_login()
        html = self._get("/ParecerTecnico/ParecerFinalizado")
        if self._ainda_login(html):
            self.logado = False
            self.login()
            html = self._get("/ParecerTecnico/ParecerFinalizado")
        campos = _campos_form(html)
        campos["ctl00$body$txtnomecliente"] = (nome_cliente or "").strip()
        campos["ctl00$body$dropconjuntopesquisa"] = conjunto_id or "SELECIONE"
        campos["ctl00$body$btnpesquisarparecer"] = "Pesquisar"
        html = self._post("/ParecerTecnico/ParecerFinalizado", campos)
        campos = _campos_form(html)
        if "ctl00$body$droppagesize" in campos and campos.get("ctl00$body$droppagesize") != "0":
            campos["ctl00$body$droppagesize"] = "0"
            campos["__EVENTTARGET"] = "ctl00$body$droppagesize"
            campos["__EVENTARGUMENT"] = ""
            campos.pop("ctl00$body$btnpesquisarparecer", None)
            html = self._post("/ParecerTecnico/ParecerFinalizado", campos)
        pareceres: list[ParecerFinalizado] = []
        for cels in _celulas_html_tabela(html, "body_gridparecer"):
            if not cels:
                continue
            texto0 = _texto_html(cels[0]).lower()
            if "mutu" in texto0 and "cpf" not in texto0:
                continue
            dados = _parse_celula_mutuario(cels[0])
            if not dados["nome"] or not dados["id_mutuario"]:
                continue
            data = _texto_html(cels[1]) if len(cels) > 1 else ""
            pareceres.append(
                ParecerFinalizado(
                    nome=dados["nome"],
                    id_mutuario=dados["id_mutuario"],
                    cpf=dados["cpf"],
                    conjunto=dados["conjunto"],
                    conjunto_id=conjunto_id or "",
                    endereco=dados["endereco"],
                    bloco=dados["bloco"],
                    apartamento=dados["apartamento"],
                    cidade=dados["cidade"],
                    uf=dados["uf"],
                    data=data,
                )
            )
        total_txt = _valor_hidden(html, "body_hfTotalGridImoveis")
        try:
            total = int(total_txt)
        except ValueError:
            total = len(pareceres)
        return ResultadoPesquisaPareceres(pareceres=pareceres, total=total)
