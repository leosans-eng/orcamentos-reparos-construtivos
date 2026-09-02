"""Carrega ícones SVG de assets/icons para uso em widgets Tkinter."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from app_paths import asset_path

try:
    from tksvg import SvgImage
except ImportError:
    SvgImage = None  # type: ignore[misc, assignment]

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = None  # type: ignore[misc, assignment]
    ImageOps = None  # type: ignore[misc, assignment]
    ImageTk = None  # type: ignore[misc, assignment]


def criar_icone_svg(
    master: tk.Misc,
    nome: str,
    *,
    altura: int,
    cor: str = "#006699",
    angulo: float = 0,
    escala_x: float = 1.0,
    escala_y: float = 1.0,
) -> tk.PhotoImage:
    """Rasteriza um SVG de assets/icons/{nome}.svg na altura indicada (px)."""
    if SvgImage is None:
        raise ImportError("Pacote 'tksvg' não instalado.")

    caminho = asset_path("icons", f"{nome}.svg")
    if caminho is None:
        raise FileNotFoundError(f"Ícone SVG não encontrado: assets/icons/{nome}.svg")

    svg_texto = caminho.read_text(encoding="utf-8")
    svg_texto = _aplicar_cor_svg(svg_texto, cor)
    if escala_x != 1.0 or escala_y != 1.0:
        svg_texto = _svg_com_escala(svg_texto, escala_x, escala_y)

    base = SvgImage(master=master, data=svg_texto, scaletoheight=altura)
    if not angulo:
        return base
    return _photo_rotacionado(master, base, angulo, altura)


def _photo_rotacionado(
    master: tk.Misc, base: tk.PhotoImage, angulo: float, tamanho: int
) -> tk.PhotoImage:
    """Gira o raster com Pillow (inversão confiável a 180°)."""
    if Image is None or ImageTk is None:
        # Fallback: tentativa via transform SVG (menos confiável no Tk).
        return base

    pil = ImageTk.getimage(base).convert("RGBA")
    # PIL: positivo = anti-horário; queremos o mesmo sentido visual do SVG (horário).
    girado = pil.rotate(
        -angulo,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    canvas = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    x = (tamanho - girado.width) // 2
    y = (tamanho - girado.height) // 2
    canvas.paste(girado, (x, y), girado)
    return ImageTk.PhotoImage(canvas, master=master)


def criar_label_icone(
    parent: tk.Misc,
    nome: str,
    *,
    altura: int = 14,
    cor: str = "#555555",
    bg: str = "#ececec",
    refs: list | None = None,
    texto: str | None = None,
    fonte: tuple = ("Arial", 9),
    fg: str = "#555555",
) -> tk.Misc:
    """Ícone SVG; com `texto`, devolve o ícone e o rótulo lado a lado."""
    icone = criar_icone_svg(parent, nome, altura=altura, cor=cor)
    if refs is not None:
        refs.append(icone)
    if not texto:
        label = tk.Label(parent, image=icone, bg=bg)
        label.image = icone  # type: ignore[attr-defined]
        return label
    grupo = tk.Frame(parent, bg=bg)
    lbl_icone = tk.Label(grupo, image=icone, bg=bg)
    lbl_icone.image = icone  # type: ignore[attr-defined]
    lbl_icone.pack(side="left")
    tk.Label(grupo, text=texto, bg=bg, fg=fg, font=fonte).pack(
        side="left", padx=(4, 0)
    )
    return grupo


class IndicadorAmpulheta(tk.Label):
    """Ampulheta: roda 180° → flip na imagem atual → roda 180° → flip (reinicia)."""

    _PASSOS_MEIA = 12
    _FRAMES_PAUSA = 8
    _INTERVALO_MS = 40
    _COR_AREIA = "#c98700"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        altura: int = 24,
        cor: str = "#006699",
        bg: str = "#ececec",
        refs: list | None = None,
    ):
        super().__init__(parent, bg=bg)
        self._frames: list = []
        self._indice = 0
        self._job = None
        self._ativo = False

        if Image is None or ImageTk is None or ImageOps is None:
            raise ImportError("Pacote 'Pillow' não instalado.")

        base_photo = _criar_ampulheta_com_areia(
            parent, altura=altura, cor_vidro=cor, cor_areia=self._COR_AREIA
        )
        atual = ImageTk.getimage(base_photo).convert("RGBA")
        if refs is not None:
            refs.append(base_photo)

        def para_photo(pil_img):
            foto = ImageTk.PhotoImage(pil_img, master=parent)
            if refs is not None:
                refs.append(foto)
            return foto

        def rotacionar(pil_img, angulo: float):
            ang = angulo % 360.0
            if abs(ang) < 0.01:
                return pil_img.copy()
            girado = pil_img.rotate(
                -ang,
                resample=Image.Resampling.BICUBIC,
                expand=True,
                fillcolor=(0, 0, 0, 0),
            )
            canvas = Image.new("RGBA", (altura, altura), (0, 0, 0, 0))
            canvas.paste(
                girado,
                ((altura - girado.width) // 2, (altura - girado.height) // 2),
                girado,
            )
            return canvas

        # Duas vezes: (rodar 180° → flip vertical da imagem resultante)
        for _ciclo in range(2):
            for i in range(self._PASSOS_MEIA + 1):
                if _ciclo == 1 and i == 0:
                    continue  # já estamos no ângulo 0 após o flip
                angulo = 180.0 * i / self._PASSOS_MEIA
                self._frames.append(para_photo(rotacionar(atual, angulo)))
            # Flip na imagem já rodada (senão coincide com o fim da rotação).
            atual = ImageOps.flip(rotacionar(atual, 180.0))
            self._frames.extend([para_photo(atual)] * self._FRAMES_PAUSA)

        self.configure(image=self._frames[0])
        self.bind("<Destroy>", self._ao_destruir)

    def iniciar(self) -> None:
        if self._ativo or not self._frames:
            return
        self._ativo = True
        if not self.winfo_ismapped():
            self.pack(expand=True)
        self._agendar()

    def parar(self) -> None:
        self._ativo = False
        self._cancelar()
        self._indice = 0
        if self._frames:
            try:
                self.configure(image=self._frames[0])
            except tk.TclError:
                pass
        try:
            if self.winfo_ismapped():
                self.pack_forget()
        except tk.TclError:
            pass

    def liberar(self) -> None:
        """Para animação e solta PhotoImages enquanto o Tk ainda existe."""
        self.parar()
        try:
            self.configure(image="")
        except tk.TclError:
            pass
        self._frames.clear()

    def _agendar(self) -> None:
        self._cancelar()
        try:
            self._job = self.after(self._INTERVALO_MS, self._tick)
        except tk.TclError:
            self._ativo = False

    def _tick(self) -> None:
        self._job = None
        if not self._ativo or not self._frames:
            return
        self._indice = (self._indice + 1) % len(self._frames)
        try:
            self.configure(image=self._frames[self._indice])
        except tk.TclError:
            self._ativo = False
            return
        self._agendar()

    def _cancelar(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None

    def _ao_destruir(self, _event=None) -> None:
        self._ativo = False
        self._cancelar()


def _criar_ampulheta_com_areia(
    master: tk.Misc,
    *,
    altura: int,
    cor_vidro: str,
    cor_areia: str,
) -> tk.PhotoImage:
    """Ampulheta com areia preenchida (visível ao inverter 180°)."""
    if SvgImage is None:
        raise ImportError("Pacote 'tksvg' não instalado.")
    caminho = asset_path("icons", "hourglass-outline.svg")
    if caminho is None:
        raise FileNotFoundError("Ícone SVG não encontrado: assets/icons/hourglass-outline.svg")

    svg_texto = caminho.read_text(encoding="utf-8")
    # 1º path = vidro (contorno); 2º path = areia (preenchimento).
    svg_texto = svg_texto.replace('stroke="currentColor"', f'stroke="{cor_vidro}"')
    svg_texto = svg_texto.replace(
        'fill="currentColor"',
        f'fill="{cor_areia}"',
    )
    # O path da areia no asset não traz fill/stroke — força preenchimento visível.
    partes = svg_texto.split("<path ", 2)
    if len(partes) == 3:
        vidro, areia_e_fim = partes[1], partes[2]
        if "fill=" not in areia_e_fim.split("/>", 1)[0]:
            areia_e_fim = f'fill="{cor_areia}" stroke="none" ' + areia_e_fim
        svg_texto = "<path ".join([partes[0], vidro, areia_e_fim])

    return SvgImage(master=master, data=svg_texto, scaletoheight=altura)


def altura_icone_botao(master: tk.Misc, estilo: str = "Compact.TButton") -> int:
    """Altura do ícone alinhada à fonte do botão."""
    try:
        especificacao = ttk.Style(master).lookup(estilo, "font")
        fonte = tkfont.Font(master=master, font=especificacao or "TkDefaultFont")
        return max(12, fonte.metrics("ascent") + fonte.metrics("descent"))
    except tk.TclError:
        return 14


def altura_icone_botao_compact(master: tk.Misc, estilo: str = "Compact.TButton") -> int:
    """Compatível com botões compactos."""
    return altura_icone_botao(master, estilo)


_COR_ICONE_DESABILITADO = "#9e9e9e"


def _anexar_icones_estado(botao: ttk.Button, icone, icone_off, command, estilo: str) -> ttk.Button:
    botao._orc_img_normal = icone  # type: ignore[attr-defined]
    botao._orc_img_disabled = icone_off  # type: ignore[attr-defined]
    botao._orc_command = command  # type: ignore[attr-defined]
    botao._orc_style = estilo  # type: ignore[attr-defined]
    return botao


def criar_botao_ttk_so_icone(
    parent: tk.Misc,
    *,
    nome_icone: str,
    command,
    estilo: str = "Compact.TButton",
    cor_icone: str | None = None,
    refs: list | None = None,
) -> ttk.Button:
    """Cria ttk.Button apenas com ícone SVG."""
    if cor_icone is None:
        cor_icone = "#000000"
    altura = altura_icone_botao(parent, estilo)
    icone = criar_icone_svg(parent, nome_icone, altura=altura, cor=cor_icone)
    icone_off = criar_icone_svg(
        parent, nome_icone, altura=altura, cor=_COR_ICONE_DESABILITADO
    )
    if refs is not None:
        refs.append(icone)
        refs.append(icone_off)
    botao = ttk.Button(
        parent,
        image=icone,
        command=command,
        style=estilo,
    )
    return _anexar_icones_estado(botao, icone, icone_off, command, estilo)


def criar_botao_ttk_com_icone(
    parent: tk.Misc,
    *,
    texto: str,
    nome_icone: str,
    command,
    estilo: str = "Compact.TButton",
    cor_icone: str | None = None,
    refs: list | None = None,
) -> ttk.Button:
    """Cria ttk.Button com ícone SVG à esquerda (compound=left)."""
    if cor_icone is None:
        cor_icone = "#000000"
    altura = altura_icone_botao(parent, estilo)
    icone = criar_icone_svg(parent, nome_icone, altura=altura, cor=cor_icone)
    icone_off = criar_icone_svg(
        parent, nome_icone, altura=altura, cor=_COR_ICONE_DESABILITADO
    )
    if refs is not None:
        refs.append(icone)
        refs.append(icone_off)
    botao = ttk.Button(
        parent,
        text=texto,
        image=icone,
        compound="left",
        command=command,
        style=estilo,
    )
    return _anexar_icones_estado(botao, icone, icone_off, command, estilo)


def _comando_inert():
    return None


def definir_estado_botao_icone(botao: ttk.Button, estado: str) -> None:
    """
    Desabilita visualmente sem usar state=disabled do ttk.

    O estado nativo do ttk clareia a imagem SVG e deixa um retângulo branco
    estranho; aqui só trocamos ícone/estilo e anulamos o comando.
    """
    icone_normal = getattr(botao, "_orc_img_normal", None)
    icone_off = getattr(botao, "_orc_img_disabled", None)
    comando = getattr(botao, "_orc_command", None)
    estilo = getattr(botao, "_orc_style", None) or botao.cget("style")

    if str(estado) == "disabled":
        kwargs = {
            "state": "normal",
            "command": _comando_inert,
            "style": "Muted.Compact.TButton",
        }
        if icone_off is not None:
            kwargs["image"] = icone_off
        botao.configure(**kwargs)
        return

    kwargs = {
        "state": "normal",
        "style": estilo,
    }
    if comando is not None:
        kwargs["command"] = comando
    if icone_normal is not None:
        kwargs["image"] = icone_normal
    botao.configure(**kwargs)


_COR_VERDE_INSERIR = "#2e7d32"


def criar_botao_inserir_prominente(
    parent: tk.Misc,
    *,
    texto: str,
    command,
    refs: list | None = None,
) -> tk.Button:
    """Botão 'Inserir' proeminente: fundo claro, borda verde e ícone preenchido."""
    fonte = tkfont.Font(family="Arial", size=9)
    altura_icone = max(12, fonte.metrics("ascent") + fonte.metrics("descent"))
    icone = criar_icone_svg(
        parent, "add-circle", altura=altura_icone, cor=_COR_VERDE_INSERIR
    )
    if refs is not None:
        refs.append(icone)
    return tk.Button(
        parent,
        text=texto,
        image=icone,
        compound="left",
        command=command,
        font=fonte,
        bg="#fafafa",
        fg=_COR_VERDE_INSERIR,
        activebackground="#f8f3f3",
        activeforeground="#1b5e20",
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=_COR_VERDE_INSERIR,
        highlightcolor=_COR_VERDE_INSERIR,
        padx=9,
        pady=3,
        cursor="hand2",
    )


def _aplicar_cor_svg(svg_texto: str, cor: str) -> str:
    svg_texto = svg_texto.replace('stroke="currentColor"', f'stroke="{cor}"')
    svg_texto = svg_texto.replace('fill="currentColor"', f'fill="{cor}"')
    if 'fill="none"' not in svg_texto and f'fill="{cor}"' not in svg_texto:
        svg_texto = svg_texto.replace("<path ", f'<path fill="{cor}" ')
    return svg_texto


def _svg_com_rotacao(svg_texto: str, angulo: float) -> str:
    """Envolve o conteúdo do SVG em um <g transform="rotate(...)">."""
    inicio = svg_texto.find(">")
    fim = svg_texto.rfind("</svg>")
    if inicio < 0 or fim < 0 or fim <= inicio:
        return svg_texto
    abertura = svg_texto[: inicio + 1]
    miolo = svg_texto[inicio + 1 : fim]
    fechamento = svg_texto[fim:]
    # viewBox padrão dos ícones Ionicons: 0 0 512 512
    return (
        f'{abertura}<g transform="rotate({angulo:.2f} 256 256)">'
        f"{miolo}</g>{fechamento}"
    )


def _svg_com_escala(svg_texto: str, escala_x: float, escala_y: float) -> str:
    """Escala em torno do centro (Y < 0 inverte cima↔baixo; X < 0 espelha no giro)."""
    inicio = svg_texto.find(">")
    fim = svg_texto.rfind("</svg>")
    if inicio < 0 or fim < 0 or fim <= inicio:
        return svg_texto
    abertura = svg_texto[: inicio + 1]
    miolo = svg_texto[inicio + 1 : fim]
    fechamento = svg_texto[fim:]
    return (
        f'{abertura}<g transform="translate(256 256) '
        f'scale({escala_x:.4f} {escala_y:.4f}) translate(-256 -256)">'
        f"{miolo}</g>{fechamento}"
    )
