import ctypes
import sys
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import ttk

from app_paths import icon_path

COR_BORDA_PADRAO = "#006699"
COR_BORDA_HOVER = "#004466"
COR_FUNDO_CARTAO = "#ffffff"
COR_FUNDO_HOVER = "#f5fafc"
COR_TITULO_PADRAO = "#006699"
COR_TITULO_HOVER = "#004466"

PLACEHOLDER_ESTADO = "— Selecione —"
FUSO_HORARIO_BRASIL = timezone(timedelta(hours=-3))


def formatar_data_iso_brasil(iso_texto: str) -> str:
    """Formata data/hora ISO (UTC) para exibição em GMT-3."""
    if not iso_texto:
        return "—"
    try:
        texto = str(iso_texto).replace("Z", "+00:00")
        dt = datetime.fromisoformat(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(FUSO_HORARIO_BRASIL).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(iso_texto)


def valores_combo_estado(estados):
    return [PLACEHOLDER_ESTADO] + list(estados)


def estado_do_combo(valor):
    texto = (valor or "").strip()
    if not texto or texto == PLACEHOLDER_ESTADO:
        return ""
    return texto


def aplicar_icone_janela(janela):
    """Aplica o ícone do ORC em janelas pop-up (Toplevel)."""
    icone = icon_path()
    if icone is None:
        return
    try:
        janela.iconbitmap(icone)
    except tk.TclError:
        pass


def preparar_toplevel(janela):
    """Oculta o Toplevel até centralizar_janela exibi-lo na posição correta."""
    try:
        janela.withdraw()
    except tk.TclError:
        pass


def _obter_area_util_tela(janela, parent=None):
    """Retorna (x, y, largura, altura) da área visível do monitor (sem barra de tarefas)."""
    referencia = janela
    if parent is not None:
        try:
            if parent.winfo_exists():
                referencia = parent
        except tk.TclError:
            pass

    if sys.platform == "win32":
        try:
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            user32 = ctypes.windll.user32
            hwnd = int(referencia.winfo_id())
            monitor = user32.MonitorFromWindow(hwnd, 2)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                area = info.rcWork
                return (
                    area.left,
                    area.top,
                    area.right - area.left,
                    area.bottom - area.top,
                )
        except (AttributeError, OSError, tk.TclError, TypeError, ValueError):
            pass

    try:
        return (
            referencia.winfo_vrootx(),
            referencia.winfo_vrooty(),
            referencia.winfo_vrootwidth(),
            referencia.winfo_vrootheight(),
        )
    except tk.TclError:
        pass

    return 0, 0, janela.winfo_screenwidth(), janela.winfo_screenheight()


def _medir_dimensoes_janela(janela):
    """Obtém largura/altura reais após o layout, sem flash visível na tela."""
    janela.update_idletasks()
    alpha_oculto = False
    try:
        janela.attributes("-alpha", 0.0)
        alpha_oculto = True
    except tk.TclError:
        janela.geometry("-20000-20000")

    try:
        janela.deiconify()
    except tk.TclError:
        pass
    janela.update_idletasks()

    largura = janela.winfo_width()
    altura = janela.winfo_height()
    if largura <= 1:
        largura = janela.winfo_reqwidth()
    if altura <= 1:
        altura = janela.winfo_reqheight()

    return largura, altura, alpha_oculto


def centralizar_janela(janela, parent=None):
    largura, altura, alpha_oculto = _medir_dimensoes_janela(janela)

    area_x, area_y, area_largura, area_altura = _obter_area_util_tela(janela, parent)
    x = area_x + max(0, (area_largura - largura) // 2)
    y = area_y + max(0, (area_altura - altura) // 2)
    janela.geometry(f"+{x}+{y}")
    janela.update_idletasks()
    if alpha_oculto:
        try:
            janela.attributes("-alpha", 1.0)
        except tk.TclError:
            pass


def focar_entrada_apos_exibir(entrada, *, selecionar=False):
    """Coloca o foco no campo após a janela ser exibida e centralizada."""
    def aplicar():
        try:
            if not entrada.winfo_exists():
                return
            entrada.focus_set()
            if selecionar:
                entrada.select_range(0, "end")
                entrada.icursor("end")
        except tk.TclError:
            pass

    entrada.after_idle(aplicar)


def perguntar_texto(
    parent,
    titulo,
    mensagem,
    valor_inicial="",
    texto_ok="OK",
    *,
    largura_entrada=44,
    minsize=None,
    padding=(16, 14),
):
    """Diálogo de entrada de texto com ícone do ORC (substitui simpledialog.askstring)."""
    resultado: list[str | None] = [None]
    dialog = tk.Toplevel(parent)
    preparar_toplevel(dialog)
    dialog.title(titulo)
    aplicar_icone_janela(dialog)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(bool(minsize), False)
    if minsize:
        dialog.minsize(*minsize)
    dialog.configure(bg="#ececec")

    painel = tk.Frame(dialog, bg="#ececec", padx=padding[0], pady=padding[1])
    painel.pack(fill="both", expand=True)

    tk.Label(
        painel,
        text=mensagem,
        bg="#ececec",
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 8))

    var_texto = tk.StringVar(value=valor_inicial)
    entrada = ttk.Entry(painel, textvariable=var_texto, width=largura_entrada)
    entrada.pack(fill="x", pady=(0, 12))

    botoes = ttk.Frame(painel)
    botoes.pack(fill="x")

    def cancelar():
        dialog.destroy()

    def confirmar():
        resultado[0] = var_texto.get()
        dialog.destroy()

    ttk.Button(botoes, text="Cancelar", command=cancelar, style="Delete.TButton").pack(
        side="right", padx=(6, 0)
    )
    ttk.Button(botoes, text=texto_ok, command=confirmar, style="Add.TButton").pack(
        side="right"
    )

    entrada.bind("<Return>", lambda _e: confirmar())
    entrada.bind("<Escape>", lambda _e: cancelar())
    dialog.protocol("WM_DELETE_WINDOW", cancelar)
    centralizar_janela(dialog, parent)
    focar_entrada_apos_exibir(entrada, selecionar=True)
    parent.wait_window(dialog)
    return resultado[0]


def centralizar_janela_principal(janela, largura, altura):
    janela.update_idletasks()
    area_x, area_y, area_largura, area_altura = _obter_area_util_tela(janela)
    x = area_x + max(0, (area_largura - largura) // 2)
    y = area_y + max(0, (area_altura - altura) // 2)
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


def _configurar_botao_colorido(style, nome, *, background, active, pressed, padding):
    style.configure(
        nome,
        background=background,
        foreground="black",
        borderwidth=1,
        focuscolor="none",
        padding=padding,
    )
    style.map(
        nome,
        background=[
            ("disabled", "#e0e0e0"),
            ("active", active),
            ("pressed", pressed),
        ],
        foreground=[
            ("disabled", "#9e9e9e"),
            ("active", "black"),
            ("pressed", "black"),
        ],
    )


def _us_para_br_numero(texto_us: str) -> str:
    """Converte número em texto US (1,234.56) para BR (1.234,56)."""
    return texto_us.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_br(valor) -> str:
    """Formata valor em reais com separador de milhar (ex.: R$ 3.056.524,10)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return "R$ " + _us_para_br_numero(f"{numero:,.2f}")


def formatar_decimal_br(valor, casas: int = 4) -> str:
    """Formata decimal/quantidade com ponto nos milhares e vírgula decimal."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if casas <= 0 or v == int(v):
        return _us_para_br_numero(f"{int(v):,}")
    texto_us = f"{v:,.{casas}f}".rstrip("0").rstrip(".")
    return _us_para_br_numero(texto_us)


def formatar_quantidade_edicao(valor, casas: int = 4) -> str:
    """Quantidade para campos de edição — sem separador de milhar."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if casas <= 0 or v == int(v):
        return str(int(v))
    texto = f"{v:.{casas}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def parse_decimal_br(texto) -> float:
    """Interpreta número em notação brasileira (vírgula decimal, ponto opcional de milhar)."""
    normalizado = str(texto).strip()
    if not normalizado:
        raise ValueError("valor vazio")
    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    return float(normalizado)


def parse_quantidade_expressao(texto) -> float:
    """
    Interpreta quantidade com suporte a expressão aritmética simples.

    Exemplos: ``12,5``, ``10*15``, ``2+3*4``, ``(1,5+2)*3``.
    Aceita ``+ - * /`` e parênteses; vírgula como decimal.
    """
    import ast
    import operator as op
    import re

    bruto = str(texto).strip().replace(" ", "")
    if not bruto:
        raise ValueError("valor vazio")

    # Sem operadores: mantém regra brasileira (ponto de milhar + vírgula decimal).
    if not re.search(r"[+\-*/()]", bruto):
        return parse_decimal_br(bruto)

    # Em expressões, vírgula é sempre decimal (sem milhar).
    expressao = bruto.replace(",", ".")
    if not re.fullmatch(r"[0-9+\-*/().]+", expressao):
        raise ValueError("expressão inválida")

    operadores = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.USub: op.neg,
        ast.UAdd: op.pos,
    }

    def _avaliar(no):
        if isinstance(no, ast.Expression):
            return _avaliar(no.body)
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
            return float(no.value)
        if isinstance(no, ast.UnaryOp) and type(no.op) in operadores:
            return operadores[type(no.op)](_avaliar(no.operand))
        if isinstance(no, ast.BinOp) and type(no.op) in operadores:
            esquerdo = _avaliar(no.left)
            direito = _avaliar(no.right)
            if isinstance(no.op, ast.Div) and direito == 0:
                raise ValueError("divisão por zero")
            return operadores[type(no.op)](esquerdo, direito)
        raise ValueError("expressão inválida")

    try:
        arvore = ast.parse(expressao, mode="eval")
        return float(_avaliar(arvore))
    except (SyntaxError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError("expressão inválida") from exc


def configurar_estilos_ttk(root):
    """Estilos achatados de botões (mesmo padrão do Gerador de Relatórios Fotográficos)."""
    if getattr(root, "_orc_estilos_ttk", False):
        return
    style = ttk.Style(root)
    try:
        style.theme_use("")
    except tk.TclError:
        pass

    for nome, bg, active, pressed, padding in (
        ("Add.TButton", "#2e7d32", "#43a047", "#1b5e20", (8, 3)),
        ("Add.Compact.TButton", "#2e7d32", "#43a047", "#1b5e20", (4, 1)),
        ("Delete.TButton", "#c62828", "#e53935", "#b71c1c", (8, 3)),
        ("Delete.Compact.TButton", "#c62828", "#e53935", "#b71c1c", (4, 1)),
        ("Edit.TButton", "#1565c0", "#1976d2", "#0d47a1", (8, 3)),
        ("Edit.Compact.TButton", "#1565c0", "#1976d2", "#0d47a1", (4, 1)),
        ("Accent.TButton", "#e65100", "#f57c00", "#bf360c", (8, 3)),
        ("Accent.Compact.TButton", "#e65100", "#f57c00", "#bf360c", (4, 1)),
        ("Save.TButton", "#2e7d32", "#43a047", "#1b5e20", (8, 3)),
    ):
        _configurar_botao_colorido(
            style, nome, background=bg, active=active, pressed=pressed, padding=padding
        )

    style.configure(
        "Secondary.TButton",
        background="#eceff1",
        foreground="#37474f",
        borderwidth=1,
        focuscolor="none",
        padding=(8, 3),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", "#cfd8dc"), ("pressed", "#b0bec5")],
        foreground=[("active", "#263238"), ("pressed", "#263238")],
    )
    style.configure("Compact.TButton", padding=(4, 1), focuscolor="none")
    style.map(
        "Compact.TButton",
        background=[
            ("disabled", "#e0e0e0"),
            ("pressed", "#d5d5d5"),
            ("active", "#e8e8e8"),
        ],
        foreground=[
            ("disabled", "#9e9e9e"),
        ],
    )
    style.configure(
        "Secondary.Compact.TButton",
        background="#eceff1",
        foreground="#37474f",
        borderwidth=1,
        focuscolor="none",
        padding=(4, 1),
    )
    style.map(
        "Secondary.Compact.TButton",
        background=[
            ("disabled", "#e0e0e0"),
            ("active", "#cfd8dc"),
            ("pressed", "#b0bec5"),
        ],
        foreground=[
            ("disabled", "#9e9e9e"),
            ("active", "#263238"),
            ("pressed", "#263238"),
        ],
    )
    style.configure(
        "Muted.Compact.TButton",
        background="#e8e8e8",
        foreground="#9e9e9e",
        borderwidth=1,
        focuscolor="none",
        padding=(4, 1),
    )
    style.map(
        "Muted.Compact.TButton",
        background=[("active", "#e8e8e8"), ("pressed", "#e8e8e8")],
        foreground=[("active", "#9e9e9e"), ("pressed", "#9e9e9e")],
    )
    root._orc_estilos_ttk = True


def confirmar_exclusao_com_espera(
    parent,
    titulo,
    mensagem,
    texto_confirmar,
    segundos=5,
    estilo_confirmar="Delete.TButton",
):
    """Diálogo de exclusão com contagem regressiva antes de habilitar a confirmação."""
    dialog = tk.Toplevel(parent)
    preparar_toplevel(dialog)
    dialog.title(titulo)
    aplicar_icone_janela(dialog)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)

    resultado = {"confirmed": False}
    restante = segundos
    timer_id: list[str | None] = [None]

    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=mensagem, wraplength=380, justify="center").pack(pady=(0, 12))

    countdown_var = tk.StringVar(value=f"Aguarde {restante}s para confirmar...")
    ttk.Label(frame, textvariable=countdown_var, foreground="#c62828").pack(pady=(0, 12))

    botoes = ttk.Frame(frame)
    botoes.pack(fill="x")

    def cancelar():
        if timer_id[0] is not None:
            dialog.after_cancel(timer_id[0])
        dialog.destroy()

    def confirmar():
        resultado["confirmed"] = True
        cancelar()

    btn_confirmar = ttk.Button(
        botoes,
        text=texto_confirmar,
        command=confirmar,
        state="disabled",
        style=estilo_confirmar,
    )
    ttk.Button(botoes, text="Cancelar", command=cancelar, style="Secondary.TButton").pack(
        side="right", padx=(6, 0)
    )
    btn_confirmar.pack(side="right")

    def tick():
        nonlocal restante
        restante -= 1
        if restante > 0:
            countdown_var.set(f"Aguarde {restante}s para confirmar...")
            timer_id[0] = dialog.after(1000, tick)
        else:
            countdown_var.set("")
            btn_confirmar.config(state="normal")

    timer_id[0] = dialog.after(1000, tick)
    dialog.protocol("WM_DELETE_WINDOW", cancelar)
    centralizar_janela(dialog, parent)
    parent.wait_window(dialog)
    return bool(resultado["confirmed"])


def _ponteiro_dentro(widget):
    x, y = widget.winfo_pointerx(), widget.winfo_pointery()
    alvo = widget.winfo_containing(x, y)
    while alvo:
        if alvo == widget:
            return True
        alvo = alvo.master
    return False


def aplicar_hover_cartao(
    cartao,
    widgets,
    cor_borda_normal=COR_BORDA_PADRAO,
    cor_borda_hover=COR_BORDA_HOVER,
    cor_fundo_normal=COR_FUNDO_CARTAO,
    cor_fundo_hover=COR_FUNDO_HOVER,
):
    """Hover estável: funciona ao mover o mouse entre o cartão e os labels internos."""
    estado = {"hover": False, "job": None}

    def aplicar(estilo_hover):
        cor_borda = cor_borda_hover if estilo_hover else cor_borda_normal
        cor_fundo = cor_fundo_hover if estilo_hover else cor_fundo_normal
        cartao.configure(highlightbackground=cor_borda, bg=cor_fundo)
        for w in widgets:
            try:
                if isinstance(w, (tk.Label, tk.Frame)):
                    opts = {"bg": cor_fundo}
                    if isinstance(w, tk.Label):
                        try:
                            cor_fg = w.cget("fg")
                        except tk.TclError:
                            cor_fg = ""
                        if cor_fg in (COR_TITULO_PADRAO, COR_TITULO_HOVER, cor_borda_normal):
                            opts["fg"] = COR_TITULO_HOVER if estilo_hover else COR_TITULO_PADRAO
                    w.configure(**opts)
            except tk.TclError:
                pass

    def verificar():
        estado["job"] = None
        dentro = _ponteiro_dentro(cartao)
        if dentro and not estado["hover"]:
            estado["hover"] = True
            aplicar(True)
        elif not dentro and estado["hover"]:
            estado["hover"] = False
            aplicar(False)

    def agendar_verificacao(_event=None):
        if estado["job"] is not None:
            cartao.after_cancel(estado["job"])
        estado["job"] = cartao.after(40, verificar)

    def ao_entrar(_event=None):
        if estado["job"] is not None:
            cartao.after_cancel(estado["job"])
            estado["job"] = None
        if not estado["hover"]:
            estado["hover"] = True
            aplicar(True)

    cartao.bind("<Enter>", ao_entrar)
    cartao.bind("<Leave>", agendar_verificacao)
    for w in widgets:
        w.bind("<Enter>", ao_entrar)
        w.bind("<Leave>", agendar_verificacao)


def criar_botao_voltar(parent, command, bg_parent="#ececec"):
    """Botão 'Voltar ao início' no mesmo padrão visual dos cartões do Hub."""
    btn = tk.Frame(
        parent,
        bg=COR_FUNDO_CARTAO,
        highlightbackground=COR_BORDA_PADRAO,
        highlightthickness=2,
        cursor="hand2",
    )
    lbl = tk.Label(
        btn,
        text="← Voltar",
        font=("Arial", 10, "bold"),
        fg=COR_TITULO_PADRAO,
        bg=COR_FUNDO_CARTAO,
        padx=16,
        pady=6,
    )
    lbl.pack()

    def ao_clicar(_event=None):
        command()

    btn.bind("<Button-1>", ao_clicar)
    lbl.bind("<Button-1>", ao_clicar)
    aplicar_hover_cartao(btn, [lbl])

    return btn


def vincular_tooltip(widget, texto: str):
    """Exibe texto ao passar o mouse (tooltip simples)."""
    estado = {"janela": None}

    def _mostrar(_event):
        if estado["janela"] is not None:
            return
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        janela = tk.Toplevel(widget)
        janela.wm_overrideredirect(True)
        janela.wm_geometry(f"+{x}+{y}")
        tk.Label(
            janela,
            text=texto,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("Arial", 9),
            padx=6,
            pady=3,
        ).pack()
        estado["janela"] = janela

    def _esconder(_event):
        if estado["janela"] is not None:
            estado["janela"].destroy()
            estado["janela"] = None

    widget.bind("<Enter>", _mostrar)
    widget.bind("<Leave>", _esconder)


def criar_barra_modulo(
    parent,
    titulo,
    on_voltar,
    *,
    texto_referencia=None,
    montar_acoes_antes_referencia=None,
    montar_acoes_apos_titulo=None,
    montar_acoes_antes_titulo=None,
    bg="#ececec",
):
    """Barra superior: Voltar ao início, título da página e referência opcional na mesma linha."""
    barra = tk.Frame(parent, bg=bg)
    barra.pack(fill="x", padx=10, pady=(8, 8))

    criar_botao_voltar(barra, on_voltar, bg_parent=bg).pack(side="left")

    if montar_acoes_antes_titulo is not None:
        montar_acoes_antes_titulo(barra)

    tk.Label(
        barra,
        text=titulo,
        font=("Arial", 14, "bold"),
        fg=COR_TITULO_PADRAO,
        bg=bg,
    ).pack(side="left", padx=(12, 4))

    if montar_acoes_apos_titulo is not None:
        montar_acoes_apos_titulo(barra)

    label_referencia = None
    if texto_referencia is not None or montar_acoes_antes_referencia is not None:
        lado_direito = tk.Frame(barra, bg=bg)
        lado_direito.pack(side="right")

        if texto_referencia is not None:
            label_referencia = tk.Label(
                lado_direito,
                text=texto_referencia,
                font=("Arial", 9),
                fg="#666666",
                bg=bg,
            )
            label_referencia.pack(side="right")

        if montar_acoes_antes_referencia is not None:
            montar_acoes_antes_referencia(lado_direito)

    return label_referencia


class ControleAtualizacaoPagina:
    """Botão 'Atualizar página' com barrinha de progresso ao lado."""

    def __init__(self, parent, *, command, refs, bg="#ececec"):
        from ui.icones import criar_botao_ttk_so_icone

        self.botao = criar_botao_ttk_so_icone(
            parent,
            nome_icone="sync-outline",
            command=command,
            estilo="Compact.TButton",
            cor_icone="#006699",
            refs=refs,
        )
        self.botao.pack(side="left", padx=(0, 6))
        vincular_tooltip(self.botao, "Atualizar página")

        self.barra = ttk.Progressbar(
            parent,
            mode="indeterminate",
            length=72,
        )
        self.label = tk.Label(
            parent,
            text="",
            bg=bg,
            fg="#666666",
            font=("Arial", 8),
        )

    def definir_ativo(self, ativo: bool):
        if ativo:
            self.botao.state(["disabled"])
            if not self.barra.winfo_ismapped():
                self.barra.pack(side="left", padx=(0, 6))
            if not self.label.winfo_ismapped():
                self.label.pack(side="left", padx=(0, 8))
            self.label.config(text="Atualizando…")
            self.barra.start(12)
            return

        try:
            self.barra.stop()
        except tk.TclError:
            pass
        if self.barra.winfo_ismapped():
            self.barra.pack_forget()
        if self.label.winfo_ismapped():
            self.label.pack_forget()
        self.label.config(text="")
        self.botao.state(["!disabled"])
