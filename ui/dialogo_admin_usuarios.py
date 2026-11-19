"""Administração de usuários da API (somente admin)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import traceback
from tkinter import messagebox, ttk

from core.api_client import get_client
from core.api_exceptions import ApiError
from ui.icones import IndicadorAmpulheta, criar_botao_ttk_com_icone, definir_estado_botao_icone
from ui.temas import aplicar_chrome_dialogo
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    confirmar_exclusao_com_espera,
    criar_botao_cancelar,
    criar_botao_fechar,
    focar_entrada_apos_exibir,
    montar_opcoes_senha,
    preparar_toplevel,
)


def _cor_aviso(cores) -> str:
    return "#ffb74d" if cores.escuro else "#b26a00"


def _eh_admin(usuario: dict | None) -> bool:
    if not usuario:
        return False
    permissoes = usuario.get("permissions") or {}
    return bool(permissoes.get("admin"))


def _rotulo_ativo(ativo: bool) -> str:
    return "Ativo" if ativo else "Inativo"


def _rotulo_perfil(usuario: dict) -> str:
    return "Admin" if _eh_admin(usuario) else "Usuário"


class DialogoNovoUsuario(tk.Toplevel):
    def __init__(self, parent, on_criado):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        estilos = self._estilos
        fundo = cores.fundo
        cartao = cores.fundo_cartao
        self.on_criado = on_criado
        self._refs_icones: list = []
        self.title("Novo usuário")
        aplicar_icone_janela(self)
        self.configure(bg=fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=fundo, padx=20, pady=16)
        painel.pack(fill="x")

        tk.Label(
            painel,
            text="Novo usuário",
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
        inner.columnconfigure(0, weight=1)

        self.var_usuario = tk.StringVar()
        self.var_senha = tk.StringVar()
        self.var_confirmar = tk.StringVar()
        self.var_admin = tk.BooleanVar(value=False)

        self._entrada_usuario = self._campo(inner, "Usuário:", self.var_usuario, 0, mostrar=None)
        entrada_senha = self._campo(inner, "Senha:", self.var_senha, 2, mostrar="•")
        entrada_confirmar = self._campo(
            inner, "Confirmar senha:", self.var_confirmar, 4, mostrar="•"
        )
        montar_opcoes_senha(
            inner,
            [self._entrada_usuario, entrada_senha, entrada_confirmar],
            ao_confirmar=self._confirmar,
            bg=cartao,
            cor_aviso=_cor_aviso(cores),
        ).grid(row=6, column=0, sticky="ew", pady=(8, 0))

        ttk.Checkbutton(
            inner,
            text="Administrador",
            variable=self.var_admin,
            style="Cartao.TCheckbutton",
        ).grid(row=7, column=0, sticky="w", pady=(10, 0))

        self._lbl_erro = tk.Label(
            painel,
            text="",
            font=("Arial", 9),
            fg=cores.perigo,
            bg=fundo,
            wraplength=340,
            justify="left",
        )
        self._lbl_erro.pack(anchor="w", pady=(10, 8))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Criar",
            nome_icone="add-circle-outline",
            command=self._confirmar,
            estilo=estilos.adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self._entrada_usuario)

    def _campo(self, parent, rotulo, variavel, linha, *, mostrar):
        cores = self._cores
        tk.Label(
            parent,
            text=rotulo,
            bg=cores.fundo_cartao,
            fg=cores.texto_suave,
            font=("Arial", 9),
        ).grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 8, 4))
        kwargs = {"textvariable": variavel, "width": 34}
        if mostrar is not None:
            kwargs["show"] = mostrar
        entrada = ttk.Entry(parent, **kwargs)
        entrada.grid(row=linha + 1, column=0, sticky="ew")
        return entrada

    def _confirmar(self):
        username = self.var_usuario.get().strip()
        senha = self.var_senha.get()
        confirmar = self.var_confirmar.get()
        if len(username) < 2:
            self._lbl_erro.config(text="Informe um usuário com pelo menos 2 caracteres.")
            return
        if len(senha) < 6:
            self._lbl_erro.config(text="A senha deve ter pelo menos 6 caracteres.")
            return
        if senha != confirmar:
            self._lbl_erro.config(text="A confirmação não confere com a senha.")
            return
        try:
            criado = get_client().criar_usuario(
                username,
                senha,
                admin=self.var_admin.get(),
            )
        except ApiError as exc:
            self._lbl_erro.config(text=exc.mensagem)
            return
        self.on_criado(criado)
        self.destroy()


class DialogoRedefinirSenha(tk.Toplevel):
    def __init__(self, parent, user_id: str, username: str, on_ok):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        estilos = self._estilos
        fundo = cores.fundo
        cartao = cores.fundo_cartao
        self.user_id = user_id
        self.on_ok = on_ok
        self._refs_icones: list = []
        self.title("Redefinir senha")
        aplicar_icone_janela(self)
        self.configure(bg=fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=fundo, padx=20, pady=16)
        painel.pack(fill="x")

        tk.Label(
            painel,
            text=f'Redefinir senha de "{username}"',
            font=("Arial", 12, "bold"),
            fg=cores.texto,
            bg=fundo,
            wraplength=340,
            justify="left",
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

        self.var_nova = tk.StringVar()
        self.var_confirmar = tk.StringVar()
        self._entrada_nova = self._campo(inner, "Nova senha:", self.var_nova, 0)
        entrada_confirmar = self._campo(inner, "Confirmar nova senha:", self.var_confirmar, 2)
        montar_opcoes_senha(
            inner,
            [self._entrada_nova, entrada_confirmar],
            ao_confirmar=self._confirmar,
            bg=cartao,
            cor_aviso=_cor_aviso(cores),
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))

        self._lbl_erro = tk.Label(
            painel,
            text="",
            font=("Arial", 9),
            fg=cores.perigo,
            bg=fundo,
            wraplength=340,
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
        focar_entrada_apos_exibir(self._entrada_nova)

    def _campo(self, parent, rotulo, variavel, linha):
        cores = self._cores
        tk.Label(
            parent,
            text=rotulo,
            bg=cores.fundo_cartao,
            fg=cores.texto_suave,
            font=("Arial", 9),
        ).grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 8, 4))
        entrada = ttk.Entry(parent, textvariable=variavel, width=34, show="•")
        entrada.grid(row=linha + 1, column=0, sticky="ew")
        return entrada

    def _confirmar(self):
        senha = self.var_nova.get()
        confirmar = self.var_confirmar.get()
        if len(senha) < 6:
            self._lbl_erro.config(text="A senha deve ter pelo menos 6 caracteres.")
            return
        if senha != confirmar:
            self._lbl_erro.config(text="A confirmação não confere com a nova senha.")
            return
        try:
            get_client().redefinir_senha_usuario(self.user_id, senha)
        except ApiError as exc:
            self._lbl_erro.config(text=exc.mensagem)
            return
        self.on_ok()
        self.destroy()


class DialogoAdminUsuarios(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        estilos = self._estilos
        fundo = cores.fundo
        self._refs_icones: list = []
        self._usuarios: list[dict] = []
        self._me: dict | None = None
        # A lista vem do servidor numa thread (a janela não congela); o
        # resultado chega por esta fila e é lido pela própria tela.
        self._fila_lista: queue.Queue = queue.Queue()
        self._carregando = False
        self._after_lista = None
        self._ampulheta = None

        self.title("Administrar usuários")
        aplicar_icone_janela(self)
        self.configure(bg=fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(720, 440)

        painel = tk.Frame(self, bg=fundo, padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Administrar usuários",
            font=("Arial", 12, "bold"),
            fg=cores.texto,
            bg=fundo,
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            painel,
            text="Crie, ative, promova ou remova usuários da API.",
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=fundo,
        ).pack(anchor="w", pady=(0, 12))

        linha_botoes = tk.Frame(painel, bg=fundo)
        linha_botoes.pack(fill="x", pady=(0, 8))

        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Novo usuário",
            nome_icone="person-add",
            command=self._novo_usuario,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(0, 4))

        self.btn_senha = ttk.Button(
            linha_botoes,
            text="Redefinir senha",
            command=self._redefinir_senha,
            style=estilos.compacto,
            state="disabled",
            width=15,
        )
        self.btn_senha.pack(side="left", padx=(0, 4))

        # Largura fixa para "Desativar" / "Ativar" não alterar o layout.
        self.btn_ativo = ttk.Button(
            linha_botoes,
            text="Desativar",
            command=self._alternar_ativo,
            style=estilos.compacto,
            state="disabled",
            width=10,
        )
        self.btn_ativo.pack(side="left", padx=(0, 4))

        # Largura fixa para caber "Remover admin" sem esticar a janela.
        self.btn_admin = ttk.Button(
            linha_botoes,
            text="Tornar admin",
            command=self._alternar_admin,
            style=estilos.compacto_editar,
            state="disabled",
            width=14,
        )
        self.btn_admin.pack(side="left", padx=(0, 4))

        self.btn_excluir = criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Excluir",
            nome_icone="person-remove",
            command=self._excluir,
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        )
        self.btn_excluir.pack(side="left", padx=(0, 4))
        definir_estado_botao_icone(self.btn_excluir, "disabled", apagar=True)

        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Atualizar",
            nome_icone="sync-outline",
            command=self._recarregar,
            estilo=estilos.compacto,
            cor_icone=cores.titulo,
            refs=self._refs_icones,
        ).pack(side="right")

        container = tk.Frame(painel, bg=fundo)
        container.pack(fill="both", expand=True)

        colunas = ("usuario", "perfil", "status")
        self.tree = ttk.Treeview(
            container,
            columns=colunas,
            show="headings",
            height=12,
            selectmode="browse",
        )
        self.tree.heading("usuario", text="Usuário")
        self.tree.heading("perfil", text="Perfil")
        self.tree.heading("status", text="Status")
        self.tree.column("usuario", width=240, stretch=True)
        self.tree.column("perfil", width=100, anchor="center", stretch=False)
        self.tree.column("status", width=100, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar)

        rodape = tk.Frame(painel, bg=fundo)
        rodape.pack(fill="x", pady=(12, 0))
        criar_botao_fechar(rodape, self.destroy).pack(side="right")

        slot_amp = tk.Frame(rodape, bg=fundo, width=24, height=24)
        slot_amp.pack(side="left")
        slot_amp.pack_propagate(False)
        self._ampulheta = IndicadorAmpulheta(
            slot_amp, altura=18, cor=cores.titulo, bg=fundo, refs=self._refs_icones
        )
        self._lbl_carregando = tk.Label(
            rodape, text="", font=("Arial", 9), fg=cores.texto_suave, bg=fundo
        )
        self._lbl_carregando.pack(side="left", padx=(4, 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        # Abre já no tamanho que comporta "Remover admin", sem crescer ao selecionar.
        largura = max(720, self.winfo_reqwidth())
        altura = max(440, self.winfo_reqheight())
        self.geometry(f"{largura}x{altura}")
        centralizar_janela(self, parent)
        self._recarregar()

    def _usuario_selecionado(self) -> dict | None:
        selecao = self.tree.selection()
        if not selecao:
            return None
        user_id = selecao[0]
        for usuario in self._usuarios:
            if str(usuario.get("id")) == user_id:
                return usuario
        return None

    def _eh_voce(self, usuario: dict | None) -> bool:
        if not usuario or not self._me:
            return False
        return str(usuario.get("id")) == str(self._me.get("id"))

    def _ao_selecionar(self, _event=None):
        usuario = self._usuario_selecionado()
        tem = usuario is not None
        estado = "normal" if tem else "disabled"
        # Na própria conta, o servidor recusa desativar, remover admin e
        # excluir; os botões ficam desativados para nem oferecer.
        estado_proprio = "disabled" if self._eh_voce(usuario) else estado
        self.btn_senha.config(state=estado)
        self.btn_ativo.config(state=estado_proprio)
        self.btn_admin.config(state=estado_proprio)
        definir_estado_botao_icone(self.btn_excluir, estado_proprio, apagar=True)
        if not tem:
            self.btn_ativo.config(text="Desativar")
            self.btn_admin.config(text="Tornar admin")
            return
        self.btn_ativo.config(text="Desativar" if usuario.get("is_active") else "Ativar")
        self.btn_admin.config(
            text="Remover admin" if _eh_admin(usuario) else "Tornar admin"
        )

    def _preencher_lista(self, usuarios: list[dict], selecionar_id: str | None = None):
        self._usuarios = list(usuarios)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for usuario in sorted(usuarios, key=lambda u: str(u.get("username", "")).lower()):
            iid = str(usuario.get("id"))
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    usuario.get("username", "")
                    + ("  (você)" if self._eh_voce(usuario) else ""),
                    _rotulo_perfil(usuario),
                    _rotulo_ativo(bool(usuario.get("is_active"))),
                ),
            )
        if selecionar_id and self.tree.exists(selecionar_id):
            self.tree.selection_set(selecionar_id)
            self.tree.focus(selecionar_id)
            self.tree.see(selecionar_id)
        self._ao_selecionar()

    def _recarregar(self, selecionar_id: str | None = None):
        if self._carregando:
            return
        self._carregando = True
        self._lbl_carregando.config(text="Carregando usuários…")
        if self._ampulheta is not None:
            self._ampulheta.iniciar()
        fila = self._fila_lista

        def trabalho():
            try:
                cliente = get_client()
                fila.put(("ok", (cliente.obter_me(), cliente.listar_usuarios())))
            except ApiError as exc:
                fila.put(("erro", exc.mensagem))
            except Exception:
                traceback.print_exc()
                fila.put(("erro", "Não foi possível carregar a lista de usuários."))

        threading.Thread(target=trabalho, daemon=True).start()
        self._after_lista = self.after(100, lambda: self._receber_lista(selecionar_id))

    def _receber_lista(self, selecionar_id):
        self._after_lista = None
        try:
            status, dado = self._fila_lista.get_nowait()
        except queue.Empty:
            self._after_lista = self.after(100, lambda: self._receber_lista(selecionar_id))
            return
        self._carregando = False
        self._lbl_carregando.config(text="")
        if self._ampulheta is not None:
            self._ampulheta.parar()
        if status == "erro":
            messagebox.showwarning("Administrar usuários", dado, parent=self)
            return
        self._me, usuarios = dado
        self._preencher_lista(usuarios, selecionar_id=selecionar_id)

    def destroy(self):
        if self._after_lista is not None:
            try:
                self.after_cancel(self._after_lista)
            except (tk.TclError, ValueError):
                pass
            self._after_lista = None
        if self._ampulheta is not None:
            try:
                self._ampulheta.liberar()
            except tk.TclError:
                pass
            self._ampulheta = None
        super().destroy()

    def _novo_usuario(self):
        def ao_criar(criado: dict):
            messagebox.showinfo(
                "Novo usuário",
                f'Usuário "{criado.get("username")}" criado com sucesso.',
                parent=self,
            )
            self._recarregar(selecionar_id=str(criado.get("id")))

        DialogoNovoUsuario(self, ao_criar)

    def _redefinir_senha(self):
        usuario = self._usuario_selecionado()
        if usuario is None:
            return

        def ao_ok():
            messagebox.showinfo(
                "Redefinir senha",
                f'Senha de "{usuario.get("username")}" redefinida com sucesso.',
                parent=self,
            )

        DialogoRedefinirSenha(
            self,
            str(usuario.get("id")),
            str(usuario.get("username", "")),
            ao_ok,
        )

    def _alternar_ativo(self):
        usuario = self._usuario_selecionado()
        if usuario is None:
            return
        novo_ativo = not bool(usuario.get("is_active"))
        acao = "ativar" if novo_ativo else "desativar"
        if not messagebox.askyesno(
            "Status do usuário",
            f'Deseja {acao} o usuário "{usuario.get("username")}"?',
            parent=self,
        ):
            return
        try:
            atualizado = get_client().definir_usuario_ativo(
                str(usuario.get("id")),
                novo_ativo,
            )
        except ApiError as exc:
            messagebox.showwarning("Status do usuário", exc.mensagem, parent=self)
            return
        self._recarregar(selecionar_id=str(atualizado.get("id")))

    def _alternar_admin(self):
        usuario = self._usuario_selecionado()
        if usuario is None:
            return
        tornar_admin = not _eh_admin(usuario)
        if tornar_admin:
            pergunta = f'Tornar "{usuario.get("username")}" administrador?'
        else:
            pergunta = f'Remover permissão de administrador de "{usuario.get("username")}"?'
        if not messagebox.askyesno("Permissões", pergunta, parent=self):
            return
        try:
            atualizado = get_client().definir_permissoes_usuario(
                str(usuario.get("id")),
                admin=tornar_admin,
            )
        except ApiError as exc:
            messagebox.showwarning("Permissões", exc.mensagem, parent=self)
            return
        self._recarregar(selecionar_id=str(atualizado.get("id")))

    def _excluir(self):
        usuario = self._usuario_selecionado()
        if usuario is None:
            return
        if not confirmar_exclusao_com_espera(
            self,
            "Excluir usuário",
            f'Excluir o usuário "{usuario.get("username")}"?\n'
            "Esta ação não pode ser desfeita.",
            "Excluir usuário",
        ):
            return
        try:
            get_client().excluir_usuario(str(usuario.get("id")))
        except ApiError as exc:
            messagebox.showwarning("Excluir usuário", exc.mensagem, parent=self)
            return
        self._recarregar()


def usuario_atual_eh_admin() -> bool:
    cliente = get_client()
    try:
        return _eh_admin(cliente.obter_me())
    except ApiError:
        # Falha de rede/API não pode rebaixar um admin já autenticado nesta sessão.
        return _eh_admin(getattr(cliente, "_me_cache", None))


def abrir_dialogo_admin_usuarios(parent):
    DialogoAdminUsuarios(parent)
