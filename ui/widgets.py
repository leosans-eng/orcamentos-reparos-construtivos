import tkinter as tk

COR_BORDA_PADRAO = "#006699"
COR_BORDA_HOVER = "#004466"
COR_FUNDO_CARTAO = "#ffffff"
COR_FUNDO_HOVER = "#f5fafc"
COR_TITULO_PADRAO = "#006699"
COR_TITULO_HOVER = "#004466"


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
