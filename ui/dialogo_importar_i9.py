import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ui.widgets import aplicar_icone_janela, centralizar_janela

try:
    import windnd

    _SUPORTE_ARRASTAR = True
except ImportError:
    _SUPORTE_ARRASTAR = False


class DialogoImportarI9(tk.Toplevel):
    def __init__(self, parent, on_importar=None):
        super().__init__(parent)
        self.on_importar = on_importar
        self._importando = False

        self.title("Importar i9")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Importar planilha sintética do i9",
            font=("Arial", 11, "bold"),
            fg="#006699",
            bg="#ececec",
        ).pack(anchor="w")

        tk.Label(
            painel,
            text=(
                "Selecione o arquivo Excel exportado pelo i9 ou arraste-o "
                "para a área abaixo."
            ),
            bg="#ececec",
            fg="#333333",
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(8, 12))

        self.zona_arquivo = tk.Frame(
            painel,
            bg="#f5fafc",
            highlightbackground="#006699",
            highlightthickness=2,
            width=420,
            height=120,
        )
        self.zona_arquivo.pack()
        self.zona_arquivo.pack_propagate(False)

        self.label_arquivo = tk.Label(
            self.zona_arquivo,
            text="Nenhum arquivo selecionado",
            bg="#f5fafc",
            fg="#666666",
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
            bg="#ececec",
            fg="#888888",
            font=("Arial", 9),
        ).pack(pady=(8, 12))

        botoes = tk.Frame(painel, bg="#ececec")
        botoes.pack(fill="x")

        ttk.Button(
            botoes,
            text="Procurar arquivo...",
            command=self._procurar_arquivo,
            style="Compact.TButton",
        ).pack(side="left")

        ttk.Button(
            botoes,
            text="Cancelar",
            command=self.destroy,
            style="Delete.Compact.TButton",
        ).pack(side="right", padx=(8, 0))

        self.btn_importar = ttk.Button(
            botoes,
            text="Importar",
            command=self._confirmar_importacao,
            style="Add.Compact.TButton",
            state="disabled",
        )
        self.btn_importar.pack(side="right")

        self._caminho_selecionado = None
        centralizar_janela(self, parent)

    def _definir_arquivo(self, caminho: str):
        self._caminho_selecionado = caminho
        self.label_arquivo.config(
            text=caminho,
            fg="#333333",
        )
        self.btn_importar.config(state="normal")

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
