import tkinter as tk
from tkinter import ttk

from ui.icones import criar_botao_ttk_com_icone, criar_icone_svg
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    preparar_toplevel,
)

_CORES_STATUS = {
    "Atualizado": "#2e7d32",
    "Erro": "#ef6c00",
    "Crítico": "#c62828",
    "Verificando...": "#006699",
}


class DialogoConfiguracoes(tk.Toplevel):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        preparar_toplevel(self)
        self.ctx = ctx
        self._refs_icones: list = []
        self._trace_status = None
        self._trace_http = None

        self.title("Configurações")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Configurações",
            font=("Arial", 12, "bold"),
            fg="#333333",
            bg="#ececec",
        ).pack(anchor="w", pady=(0, 14))

        secao = tk.Frame(painel, bg="#ffffff", highlightbackground="#cccccc", highlightthickness=1)
        secao.pack(fill="x", pady=(0, 12))
        secao_inner = tk.Frame(secao, bg="#ffffff", padx=14, pady=12)
        secao_inner.pack(fill="x")

        tk.Label(
            secao_inner,
            text="Base SINAPI",
            font=("Arial", 10, "bold"),
            fg="#006699",
            bg="#ffffff",
        ).pack(anchor="w", pady=(0, 10))

        linha_acao = tk.Frame(secao_inner, bg="#ffffff")
        linha_acao.pack(fill="x")

        self._btn_verificar = criar_botao_ttk_com_icone(
            linha_acao,
            texto="Verificar SINAPI",
            nome_icone="sync-outline",
            command=self._verificar_sinapi,
            estilo="Compact.TButton",
            cor_icone="#006699",
            refs=self._refs_icones,
        )
        self._btn_verificar.pack(side="left")

        quadro_status = tk.Frame(linha_acao, bg="#ffffff")
        quadro_status.pack(side="left", padx=(18, 0))

        tk.Label(
            quadro_status,
            text="Status Servidor:",
            font=("Arial", 9),
            fg="#555555",
            bg="#ffffff",
        ).pack(anchor="w")

        self._lbl_status = tk.Label(
            quadro_status,
            text="",
            font=("Arial", 9, "bold"),
            bg="#ffffff",
        )
        self._lbl_status.pack(anchor="w")

        self._lbl_http = tk.Label(
            quadro_status,
            text="",
            font=("Arial", 8),
            fg="#777777",
            bg="#ffffff",
        )
        self._lbl_http.pack(anchor="w")

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(4, 0))
        ttk.Button(botoes, text="Fechar", command=self.destroy, style="Delete.TButton").pack(
            side="right"
        )

        if ctx.status_servidor_sinapi is not None:
            self._trace_status = ctx.status_servidor_sinapi.trace_add(
                "write", lambda *_: self._atualizar_status()
            )
        if ctx.http_servidor_sinapi is not None:
            self._trace_http = ctx.http_servidor_sinapi.trace_add(
                "write", lambda *_: self._atualizar_status()
            )

        self._atualizar_status()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _atualizar_status(self):
        status = "—"
        http = "—"
        if self.ctx.status_servidor_sinapi is not None:
            status = self.ctx.status_servidor_sinapi.get() or "—"
        if self.ctx.http_servidor_sinapi is not None:
            http = self.ctx.http_servidor_sinapi.get() or "—"

        cor = _CORES_STATUS.get(status, "#555555")
        self._lbl_status.config(text=status, fg=cor)

        if http and http != "—":
            self._lbl_http.config(text=f"HTTP {http}")
        else:
            self._lbl_http.config(text="")

        if status == "Verificando...":
            self._btn_verificar.state(["disabled"])
        else:
            self._btn_verificar.state(["!disabled"])

    def _verificar_sinapi(self):
        if self.ctx._sinapi_verificando:
            return
        self.ctx.aplicar_status_servidor("Verificando...", "—")
        self.ctx.iniciar_verificacao_sinapi(silencioso=True)

    def destroy(self):
        if self._trace_status is not None and self.ctx.status_servidor_sinapi is not None:
            self.ctx.status_servidor_sinapi.trace_remove("write", self._trace_status)
        if self._trace_http is not None and self.ctx.http_servidor_sinapi is not None:
            self.ctx.http_servidor_sinapi.trace_remove("write", self._trace_http)
        super().destroy()


def abrir_dialogo_configuracoes(parent, ctx):
    DialogoConfiguracoes(parent, ctx)
