import tkinter as tk
from tkinter import ttk

from app_paths import icon_path

COR_BORDA_PADRAO = "#006699"
COR_BORDA_HOVER = "#004466"
COR_FUNDO_CARTAO = "#ffffff"
COR_FUNDO_HOVER = "#f5fafc"
COR_TITULO_PADRAO = "#006699"
COR_TITULO_HOVER = "#004466"

PLACEHOLDER_ESTADO = "— Selecione —"


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


def perguntar_texto(
    parent,
    titulo,
    mensagem,
    valor_inicial="",
    texto_ok="OK",
):
    """Diálogo de entrada de texto com ícone do ORC (substitui simpledialog.askstring)."""
    resultado: list[str | None] = [None]
    dialog = tk.Toplevel(parent)
    dialog.title(titulo)
    aplicar_icone_janela(dialog)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)
    dialog.configure(bg="#ececec")

    painel = tk.Frame(dialog, bg="#ececec", padx=16, pady=14)
    painel.pack(fill="both", expand=True)

    tk.Label(
        painel,
        text=mensagem,
        bg="#ececec",
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 8))

    var_texto = tk.StringVar(value=valor_inicial)
    entrada = ttk.Entry(painel, textvariable=var_texto, width=44)
    entrada.pack(fill="x", pady=(0, 12))
    entrada.focus_set()
    entrada.select_range(0, "end")

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
    parent.wait_window(dialog)
    return resultado[0]


def centralizar_janela(janela, parent=None):
    janela.update_idletasks()
    largura = janela.winfo_width()
    altura = janela.winfo_height()
    if parent is not None and parent.winfo_exists():
        x = parent.winfo_rootx() + (parent.winfo_width() - largura) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - altura) // 2
    else:
        x = (janela.winfo_screenwidth() - largura) // 2
        y = (janela.winfo_screenheight() - altura) // 2
    janela.geometry(f"+{max(0, x)}+{max(0, y)}")


def centralizar_janela_principal(janela, largura, altura):
    janela.update_idletasks()
    x = (janela.winfo_screenwidth() - largura) // 2
    y = (janela.winfo_screenheight() - altura) // 2
    janela.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")


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
        background=[("active", active), ("pressed", pressed)],
        foreground=[("active", "black"), ("pressed", "black")],
    )


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
    style.configure("Compact.TButton", padding=(4, 1))
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
        background=[("active", "#cfd8dc"), ("pressed", "#b0bec5")],
        foreground=[("active", "#263238"), ("pressed", "#263238")],
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
                if isinstance(w, tk.Label):
                    opts = {"bg": cor_fundo}
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
        text="← Voltar ao início",
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


def criar_barra_modulo(
    parent,
    titulo,
    on_voltar,
    *,
    texto_referencia=None,
    montar_acoes_antes_referencia=None,
    bg="#ececec",
):
    """Barra superior: Voltar ao início, título da página e referência opcional na mesma linha."""
    barra = tk.Frame(parent, bg=bg)
    barra.pack(fill="x", padx=10, pady=(8, 8))

    criar_botao_voltar(barra, on_voltar, bg_parent=bg).pack(side="left")

    tk.Label(
        barra,
        text=titulo,
        font=("Arial", 14, "bold"),
        fg=COR_TITULO_PADRAO,
        bg=bg,
    ).pack(side="left", padx=(12, 8))

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
