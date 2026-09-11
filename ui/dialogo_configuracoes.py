import tkinter as tk
from tkinter import messagebox, ttk

from core.api_client import get_client
from core.api_config import carregar_config, salvar_config
from core.api_exceptions import ApiError
from ui.dialogo_admin_usuarios import abrir_dialogo_admin_usuarios, usuario_atual_eh_admin
from ui.icones import criar_botao_ttk_com_icone, definir_estado_botao_icone
from ui.temas import aplicar_chrome_dialogo, aplicar_tema, opcoes_tema, rotulo_tema, salvar_tema, tema_salvo
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_cancelar,
    criar_botao_fechar,
    focar_entrada_apos_exibir,
    preparar_toplevel,
)


def _formatar_http_status(http: str) -> str:
    if not http or http == "—":
        return ""
    partes: list[str] = []
    for trecho in http.replace("->", " ").split():
        codigo = trecho.strip()
        if codigo and codigo not in partes:
            partes.append(codigo)
    if not partes:
        return ""
    if len(partes) == 1:
        return f"HTTP {partes[0]}"
    return f"HTTP {' -> '.join(partes)}"


class DialogoTrocarSenha(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        estilos = self._estilos
        fundo = cores.fundo
        cartao = cores.fundo_cartao
        self._refs_icones: list = []
        self.title("Trocar senha")
        aplicar_icone_janela(self)
        self.configure(bg=fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=fundo, padx=20, pady=16)
        painel.pack(fill="x")

        tk.Label(
            painel,
            text="Trocar senha",
            font=("Arial", 12, "bold"),
            fg=cores.texto,
            bg=fundo,
        ).pack(anchor="w", pady=(0, 12))

        form = tk.Frame(
            painel,
            bg=cartao,
            highlightbackground=cores.borda_suave,
            highlightthickness=1,
        )
        form.pack(fill="x")
        inner = tk.Frame(form, bg=cartao, padx=14, pady=12)
        inner.pack(fill="x")

        self.var_atual = tk.StringVar()
        self.var_nova = tk.StringVar()
        self.var_confirmar = tk.StringVar()

        self._entrada_atual = self._campo(inner, "Senha atual:", self.var_atual, 0)
        self._campo(inner, "Nova senha:", self.var_nova, 2)
        entrada_confirmar = self._campo(inner, "Confirmar nova senha:", self.var_confirmar, 4)
        entrada_confirmar.bind("<Return>", lambda _e: self._confirmar())

        self._lbl_erro = tk.Label(
            painel,
            text="",
            font=("Arial", 9),
            fg=cores.perigo,
            bg=fundo,
            wraplength=320,
            justify="left",
        )
        self._lbl_erro.pack(anchor="w", pady=(10, 8))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Salvar",
            nome_icone="save-outline",
            command=self._confirmar,
            estilo=estilos.salvar,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self._entrada_atual)

    def _campo(self, parent, rotulo, variavel, linha):
        cores = self._cores
        tk.Label(
            parent,
            text=rotulo,
            bg=cores.fundo_cartao,
            fg=cores.texto_suave,
            font=("Arial", 9),
        ).grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 8, 4))
        entrada = ttk.Entry(parent, textvariable=variavel, width=32, show="•")
        entrada.grid(row=linha + 1, column=0, sticky="ew")
        return entrada

    def _confirmar(self):
        senha_atual = self.var_atual.get()
        senha_nova = self.var_nova.get()
        confirmar = self.var_confirmar.get()
        if not senha_atual:
            self._lbl_erro.config(text="Informe a senha atual.")
            return
        if not senha_nova:
            self._lbl_erro.config(text="Informe a nova senha.")
            return
        if len(senha_nova) < 6:
            self._lbl_erro.config(text="A nova senha deve ter pelo menos 6 caracteres.")
            return
        if senha_nova != confirmar:
            self._lbl_erro.config(text="A confirmação não confere com a nova senha.")
            return

        try:
            get_client().trocar_senha(senha_atual, senha_nova)
        except ApiError as exc:
            self._lbl_erro.config(text=exc.mensagem)
            return

        config = carregar_config()
        if config.get("salvar_senha"):
            salvar_config(
                config.get("base_url", ""),
                salvar_usuario=config.get("salvar_usuario", False),
                salvar_senha=True,
                usuario=config.get("usuario", ""),
                senha=senha_nova,
            )

        messagebox.showinfo(
            "Trocar senha",
            "Senha alterada com sucesso.",
            parent=self,
        )
        self.destroy()


class DialogoConfiguracoes(tk.Toplevel):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        preparar_toplevel(self)
        self.ctx = ctx
        self._refs_icones: list = []
        self._trace_status = None
        self._trace_http = None
        self._combo_tema = None
        self._trocando_tema = False
        self._job_tema = None
        self._eh_admin = usuario_atual_eh_admin()
        self.var_tema = tk.StringVar(master=self)

        self.title("Configurações")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._montar()
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _janela_app(self):
        if self.ctx.janela is not None:
            return self.ctx.janela
        master = self.master
        return master if isinstance(master, tk.Tk) else self.winfo_toplevel()

    def _soltar_traces(self):
        if self._trace_status is not None and self.ctx.status_servidor_sinapi is not None:
            try:
                self.ctx.status_servidor_sinapi.trace_remove("write", self._trace_status)
            except tk.TclError:
                pass
            self._trace_status = None
        if self._trace_http is not None and self.ctx.http_servidor_sinapi is not None:
            try:
                self.ctx.http_servidor_sinapi.trace_remove("write", self._trace_http)
            except tk.TclError:
                pass
            self._trace_http = None

    def _montar(self):
        self._soltar_traces()
        self._refs_icones.clear()
        self._combo_tema = None
        for filho in list(self.winfo_children()):
            try:
                filho.destroy()
            except tk.TclError:
                pass

        cores, estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        cartao = cores.fundo_cartao

        painel = tk.Frame(self, bg=fundo, padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Configurações",
            font=("Arial", 12, "bold"),
            fg=cores.texto,
            bg=fundo,
        ).pack(anchor="w", pady=(0, 14))

        secao = tk.Frame(painel, bg=cartao, highlightbackground=cores.borda_suave, highlightthickness=1)
        secao.pack(fill="x", pady=(0, 12))
        secao_inner = tk.Frame(secao, bg=cartao, padx=14, pady=12)
        secao_inner.pack(fill="x")

        tk.Label(
            secao_inner,
            text="Base SINAPI",
            font=("Arial", 10, "bold"),
            fg=cores.titulo,
            bg=cartao,
        ).pack(anchor="w", pady=(0, 10))

        linha_acao = tk.Frame(secao_inner, bg=cartao)
        linha_acao.pack(fill="x")

        self._btn_verificar = criar_botao_ttk_com_icone(
            linha_acao,
            texto="Verificar SINAPI",
            nome_icone="sync-outline",
            command=self._verificar_sinapi,
            estilo=estilos.compacto,
            cor_icone=cores.titulo,
            refs=self._refs_icones,
        )
        self._btn_verificar.pack(side="left")

        quadro_status = tk.Frame(linha_acao, bg=cartao)
        quadro_status.pack(side="left", padx=(18, 0))

        tk.Label(
            quadro_status,
            text="Status Servidor:",
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=cartao,
        ).pack(anchor="w")

        self._lbl_status = tk.Label(
            quadro_status,
            text="",
            font=("Arial", 9, "bold"),
            bg=cartao,
        )
        self._lbl_status.pack(anchor="w")

        self._lbl_http = tk.Label(
            quadro_status,
            text="",
            font=("Arial", 8),
            fg=cores.texto_suave,
            bg=cartao,
            wraplength=220,
            justify="left",
        )
        self._lbl_http.pack(anchor="w")

        secao_conta = tk.Frame(
            painel, bg=cartao, highlightbackground=cores.borda_suave, highlightthickness=1
        )
        secao_conta.pack(fill="x", pady=(0, 12))
        conta_inner = tk.Frame(secao_conta, bg=cartao, padx=14, pady=12)
        conta_inner.pack(fill="x")

        tk.Label(
            conta_inner,
            text="Conta",
            font=("Arial", 10, "bold"),
            fg=cores.titulo,
            bg=cartao,
        ).pack(anchor="w", pady=(0, 10))

        usuario = get_client().username or "—"
        tk.Label(
            conta_inner,
            text=f"Usuário conectado: {usuario}",
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=cartao,
        ).pack(anchor="w", pady=(0, 8))

        ttk.Button(
            conta_inner,
            text="Trocar senha",
            command=self._trocar_senha,
            style="Compact.TButton",
        ).pack(anchor="w")

        secao_aparencia = tk.Frame(
            painel, bg=cartao, highlightbackground=cores.borda_suave, highlightthickness=1
        )
        secao_aparencia.pack(fill="x", pady=(0, 12))
        aparencia_inner = tk.Frame(secao_aparencia, bg=cartao, padx=14, pady=12)
        aparencia_inner.pack(fill="x")

        tk.Label(
            aparencia_inner,
            text="Aparência",
            font=("Arial", 10, "bold"),
            fg=cores.titulo,
            bg=cartao,
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            aparencia_inner,
            text="Tema visual da interface (Hub, botões, listas e campos).",
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=cartao,
        ).pack(anchor="w", pady=(0, 8))

        janela_app = self._janela_app()
        self._opcoes_tema = opcoes_tema(janela_app)
        self._rotulo_para_id = {rotulo: tema_id for tema_id, rotulo in self._opcoes_tema}
        rotulos = [rotulo for _tema_id, rotulo in self._opcoes_tema]
        atual = rotulo_tema(tema_salvo())
        if atual not in self._rotulo_para_id:
            atual = rotulo_tema("orc")
        self.var_tema.set(atual)

        combo_tema = ttk.Combobox(
            aparencia_inner,
            textvariable=self.var_tema,
            values=rotulos,
            state="readonly",
            width=28,
        )
        combo_tema.pack(anchor="w")
        try:
            combo_tema.current(rotulos.index(atual))
        except ValueError:
            if rotulos:
                combo_tema.current(0)
        combo_tema.bind("<<ComboboxSelected>>", self._ao_trocar_tema)
        self._combo_tema = combo_tema

        if self._eh_admin:
            secao_admin = tk.Frame(
                painel, bg=cartao, highlightbackground=cores.borda_suave, highlightthickness=1
            )
            secao_admin.pack(fill="x", pady=(0, 12))
            admin_inner = tk.Frame(secao_admin, bg=cartao, padx=14, pady=12)
            admin_inner.pack(fill="x")

            tk.Label(
                admin_inner,
                text="Administração",
                font=("Arial", 10, "bold"),
                fg=cores.titulo,
                bg=cartao,
            ).pack(anchor="w", pady=(0, 6))
            tk.Label(
                admin_inner,
                text="Gerencie usuários, senhas e permissões.",
                font=("Arial", 9),
                fg=cores.texto_suave,
                bg=cartao,
            ).pack(anchor="w", pady=(0, 8))
            ttk.Button(
                admin_inner,
                text="Administrar usuários",
                command=self._abrir_admin_usuarios,
                style="Compact.TButton",
            ).pack(anchor="w")

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(4, 0))
        criar_botao_fechar(botoes, self.destroy).pack(side="right")

        if self.ctx.status_servidor_sinapi is not None:
            self._trace_status = self.ctx.status_servidor_sinapi.trace_add(
                "write", lambda *_: self._atualizar_status()
            )
        if self.ctx.http_servidor_sinapi is not None:
            self._trace_http = self.ctx.http_servidor_sinapi.trace_add(
                "write", lambda *_: self._atualizar_status()
            )

        self._atualizar_status()

    def _trocar_senha(self):
        DialogoTrocarSenha(self)

    def _fechar_lista_tema(self):
        combo = self._combo_tema
        if combo is None:
            return
        try:
            combo.tk.call("ttk::combobox::Unpost", combo)
        except tk.TclError:
            pass
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _ao_trocar_tema(self, _event=None):
        if self._trocando_tema:
            return
        tema_id = self._rotulo_para_id.get((self.var_tema.get() or "").strip(), "orc")
        self._trocando_tema = True
        self._fechar_lista_tema()
        self._job_tema = self.after(10, lambda: self._concluir_troca_tema(tema_id))

    def _concluir_troca_tema(self, tema_id):
        self._job_tema = None
        try:
            if not self.winfo_exists():
                return
            janela_app = self._janela_app()
            aplicado = aplicar_tema(janela_app, tema_id)
            salvar_tema(aplicado)
            if aplicado != tema_id:
                messagebox.showwarning(
                    "Tema visual",
                    f"Não foi possível aplicar “{rotulo_tema(tema_id)}”. "
                    "O tema Padrão ORC foi restaurado.",
                    parent=self,
                )
            self._montar()
            self.update_idletasks()
            centralizar_janela(self, self.master)
            try:
                self.grab_set()
                self.lift()
            except tk.TclError:
                pass
        finally:
            try:
                if self.winfo_exists():
                    self._trocando_tema = False
            except tk.TclError:
                pass

    def _abrir_admin_usuarios(self):
        abrir_dialogo_admin_usuarios(self)

    def _cor_status_servidor(self, status: str) -> str:
        cores = self._cores
        if status == "Atualizado":
            return "#81c784" if cores.escuro else "#2e7d32"
        if status == "Erro":
            return "#ffb74d" if cores.escuro else "#ef6c00"
        if status == "Crítico":
            return cores.perigo
        if status == "Verificando...":
            return cores.titulo
        return cores.texto_suave

    def _atualizar_status(self):
        status = "—"
        http = "—"
        if self.ctx.status_servidor_sinapi is not None:
            status = self.ctx.status_servidor_sinapi.get() or "—"
        if self.ctx.http_servidor_sinapi is not None:
            http = self.ctx.http_servidor_sinapi.get() or "—"

        self._lbl_status.config(text=status, fg=self._cor_status_servidor(status))

        if http and http != "—":
            self._lbl_http.config(text=_formatar_http_status(http))
        else:
            self._lbl_http.config(text="")

        if status == "Verificando...":
            definir_estado_botao_icone(self._btn_verificar, "disabled")
        else:
            definir_estado_botao_icone(self._btn_verificar, "normal")

    def _verificar_sinapi(self):
        if self.ctx._sinapi_verificando:
            return
        self.ctx.aplicar_status_servidor("Verificando...", "—")
        self.ctx.iniciar_verificacao_sinapi(silencioso=True)

    def destroy(self):
        job = self._job_tema
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
            self._job_tema = None
        self._soltar_traces()
        super().destroy()


def abrir_dialogo_configuracoes(parent, ctx):
    DialogoConfiguracoes(parent, ctx)
