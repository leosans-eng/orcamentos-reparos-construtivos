import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ui.icones import criar_botao_ttk_com_icone, definir_estado_botao_icone
from ui.temas import aplicar_chrome_dialogo
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_cancelar,
    preparar_toplevel,
)

try:
    import windnd

    _SUPORTE_ARRASTAR = True
except ImportError:
    _SUPORTE_ARRASTAR = False


class DialogoImportarI9(tk.Toplevel):
    def __init__(self, parent, on_importar=None):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        estilos = self._estilos
        self.on_importar = on_importar
        self._importando = False
        self._refs_icones: list = []

        self.title("Importar i9")
        aplicar_icone_janela(self)
        self.configure(bg=cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=cores.fundo, padx=20, pady=16)
        painel.pack(fill="x")

        tk.Label(
            painel,
            text="Importar planilha sintética do i9",
            font=("Arial", 11, "bold"),
            fg=cores.titulo,
            bg=cores.fundo,
        ).pack(anchor="w")

        tk.Label(
            painel,
            text=(
                "Selecione o arquivo Excel exportado pelo i9 ou arraste-o "
                "para a área abaixo."
            ),
            bg=cores.fundo,
            fg=cores.texto,
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(8, 12))

        self.zona_arquivo = tk.Frame(
            painel,
            bg=cores.fundo_destaque,
            highlightbackground=cores.borda,
            highlightthickness=2,
            width=420,
            height=120,
        )
        self.zona_arquivo.pack()
        self.zona_arquivo.pack_propagate(False)

        self.label_arquivo = tk.Label(
            self.zona_arquivo,
            text="Nenhum arquivo selecionado",
            bg=cores.fundo_destaque,
            fg=cores.texto_suave,
            wraplength=380,
            justify="center",
        )
        self.label_arquivo.place(relx=0.5, rely=0.5, anchor="center")

        if _SUPORTE_ARRASTAR:
            windnd.hook_dropfiles(
                self.zona_arquivo,
                func=self._ao_soltar_arquivo,
                force_unicode=True,
            )
            windnd.hook_dropfiles(
                self,
                func=self._ao_soltar_arquivo,
                force_unicode=True,
            )
            dica_arrastar = "Arraste o arquivo .xlsx para esta janela"
        else:
            dica_arrastar = "Use o botão abaixo para localizar o arquivo"

        tk.Label(
            painel,
            text=dica_arrastar,
            bg=cores.fundo,
            fg=cores.texto_suave,
            font=("Arial", 9),
        ).pack(pady=(8, 12))

        botoes = tk.Frame(painel, bg=cores.fundo)
        botoes.pack(fill="x")

        criar_botao_ttk_com_icone(
            botoes,
            texto="Procurar arquivo...",
            nome_icone="folder-open-outline",
            command=self._procurar_arquivo,
            estilo=estilos.compacto,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left")

        criar_botao_cancelar(botoes, self.destroy).pack(side="right", padx=(8, 0))

        self.btn_importar = criar_botao_ttk_com_icone(
            botoes,
            texto="Importar",
            nome_icone="attach-outline",
            command=self._confirmar_importacao,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        )
        self.btn_importar.pack(side="right")
        definir_estado_botao_icone(self.btn_importar, "disabled")

        self._caminho_selecionado = None
        centralizar_janela(self, parent)

    def _definir_arquivo(self, caminho: str):
        cores = self._cores
        self._caminho_selecionado = caminho
        self.label_arquivo.config(
            text=caminho,
            fg=cores.texto,
        )
        definir_estado_botao_icone(self.btn_importar, "normal")

    def _normalizar_caminho_soltado(self, caminho) -> str:
        if isinstance(caminho, bytes):
            texto = None
            for encoding in ("utf-16-le", "mbcs", "cp1252"):
                try:
                    texto = caminho.decode(encoding).rstrip("\x00")
                    break
                except UnicodeDecodeError:
                    continue
            if texto is None:
                texto = caminho.decode("utf-8", errors="replace")
        else:
            texto = str(caminho)
        return texto.strip().strip("{").strip("}").strip()

    def _ao_soltar_arquivo(self, arquivos):
        if self._importando or not arquivos:
            return
        caminho = self._normalizar_caminho_soltado(arquivos[0])
        if not caminho.lower().endswith((".xlsx", ".xlsm")):
            messagebox.showwarning(
                "Importar i9",
                "Arraste um arquivo Excel (.xlsx).",
                parent=self,
            )
            return
        self._definir_arquivo(caminho)

    def _procurar_arquivo(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar planilha i9",
            filetypes=[
                ("Planilha Excel", "*.xlsx"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if caminho:
            self._definir_arquivo(caminho)

    def _confirmar_importacao(self):
        if not self._caminho_selecionado or self.on_importar is None:
            return
        self._importando = True
        try:
            self.on_importar(self._caminho_selecionado)
            self.destroy()
        finally:
            self._importando = False
