"""Janela de desenho de metragens (ORCCAD) para a Área Comum."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.desenho_geometria import ResultadoDesenho
from core.orccad_storage import (
    EXTENSAO,
    DesenhoORCCADError,
    carregar_desenho,
    pasta_desenhos,
    salvar_desenho,
)
from ui.desenho_2d import (
    CAMPOS_DESENHO_AREA_COMUM,
    PainelDesenho2D,
    valor_para_campo,
)
from ui.icones import criar_botao_ttk_com_icone
from ui.temas import aplicar_chrome_dialogo, aplicar_tema, cores_tema, estilos_botao
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    formatar_decimal_br,
    preparar_toplevel,
    vincular_tooltip,
)


def valores_campos_desenho(
    resultados: dict[str, ResultadoDesenho | None] | ResultadoDesenho | None,
) -> dict[str, str]:
    """Preenche campos conforme a camada (externa / hall)."""
    if resultados is None:
        return {}
    if isinstance(resultados, ResultadoDesenho):
        resultados = {"externa": resultados, "hall": None}
    saida = {}
    for chave, _rotulo, tipo, camada in CAMPOS_DESENHO_AREA_COMUM:
        texto = valor_para_campo(resultados.get(camada), tipo)
        if texto:
            saida[chave] = texto
    return saida


class JanelaORCCAD:
    """Prévia autônoma ou diálogo ligado ao rascunho da Área Comum."""

    def __init__(
        self,
        parent,
        *,
        standalone: bool = False,
        on_salvar_principal=None,
        on_fechar=None,
        desenho_inicial=None,
    ):
        self.on_salvar_principal = on_salvar_principal
        self.on_fechar = on_fechar
        # Aberto pela Área Comum, o desenho alimenta o orçamento; aberto pelo
        # Hub, serve só para medir a planta e pode ser salvo em arquivo.
        self.vinculado = on_salvar_principal is not None
        self._caminho: Path | None = None
        self._desenho_salvo: dict | None = None
        self._job_feedback = None
        self._refs_icones: list = []
        self._vars_medidas: dict[tuple[str, str], tk.StringVar] = {}
        self._resultados: dict[str, ResultadoDesenho | None] = {
            "externa": None,
            "hall": None,
        }

        if standalone:
            self.janela = parent
            aplicar_tema(parent)
            aplicar_icone_janela(parent)
            cores = cores_tema(parent)
            parent.configure(bg=cores.fundo)
        else:
            self.janela = tk.Toplevel(parent)
            preparar_toplevel(self.janela)
            aplicar_chrome_dialogo(self.janela)
            aplicar_icone_janela(self.janela)
            try:
                self.janela.transient(parent.winfo_toplevel())
            except tk.TclError:
                pass
            cores = cores_tema(self.janela)

        self._cores = cores
        self._atualizar_titulo()
        self.janela.minsize(1100, 680)
        self.janela.protocol("WM_DELETE_WINDOW", self._ao_pedir_fechar)

        raiz = ttk.Frame(self.janela)
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)

        self.painel = PainelDesenho2D(raiz, on_resultado=self._ao_resultado)
        self.painel.grid(row=0, column=0, sticky="nsew")

        lado = ttk.Frame(raiz, padding=10)
        lado.grid(row=0, column=1, sticky="ns")
        raiz.columnconfigure(1, minsize=300)

        vinculado = self.vinculado
        ttk.Label(
            lado,
            text="Medidas para cálculos" if vinculado else "Medidas",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            lado,
            text=(
                "Desenhe a EXTERNA e o HALL (Offset ou do zero) "
                "para obter as medidas."
                if vinculado
                else "Desenhe a planta para ver a área e o perímetro."
            ),
            wraplength=280,
        ).pack(anchor="w", pady=(4, 10))

        self._montar_tabela_medidas(lado)

        if self.on_salvar_principal is not None:
            btn_salvar = ttk.Button(
                lado,
                text="Salvar planta no orçamento",
                command=self._salvar_principal,
            )
            btn_salvar.pack(fill="x", pady=(12, 0))
            vincular_tooltip(
                btn_salvar,
                "Grava a planta e preenche os campos da Área Comum:\n"
                "externa → fachada/cobertura; hall → laje/piso/perímetros do hall.",
            )
        else:
            self._montar_arquivo(lado)

        self._vars_campos = {}
        if vinculado:
            self._montar_campos_area_comum(lado)

        self.var_feedback = tk.StringVar(value="")
        ttk.Label(
            lado,
            textvariable=self.var_feedback,
            wraplength=280,
            foreground=cores.titulo,
        ).pack(anchor="w", pady=(10, 0))

        self.painel.vincular_atalhos(self.janela)
        if not standalone:
            centralizar_janela(self.janela, parent, largura=1280, altura=760)
        if desenho_inicial:
            self.painel.carregar(desenho_inicial)
        self._desenho_salvo = self.painel.exportar()
        self._atualizar_arquivo()
        self.janela.after_idle(lambda: self.painel.canvas.focus_set())
        self.janela.after_idle(self.painel.enquadrar_quando_visivel)
        self.janela.after(120, self.painel.enquadrar_quando_visivel)

    def _montar_campos_area_comum(self, lado):
        """Lista os campos da Área Comum que o desenho vai preencher."""
        ttk.Separator(lado).pack(fill="x", pady=(12, 8))
        ttk.Label(
            lado,
            text="Campos da Área Comum",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            lado,
            text="Externa (azul) e Hall (verde) alimentam grupos diferentes.",
            wraplength=280,
        ).pack(anchor="w", pady=(0, 6))

        camada_atual = None
        for chave, rotulo, tipo, camada in CAMPOS_DESENHO_AREA_COMUM:
            if camada != camada_atual:
                camada_atual = camada
                ttk.Label(
                    lado,
                    text="Externa" if camada == "externa" else "Hall",
                    font=("Segoe UI", 8, "bold"),
                ).pack(anchor="w", pady=(8 if camada == "hall" else 0, 2))
            linha = ttk.Frame(lado)
            linha.pack(fill="x", pady=2)
            ttk.Label(linha, text=rotulo + ":", wraplength=190).pack(
                side="left", anchor="w"
            )
            var = tk.StringVar(value="—")
            ttk.Label(linha, textvariable=var, width=12, anchor="e").pack(side="right")
            self._vars_campos[chave] = (var, tipo, camada)

    # ------------------------------------------------------------ medidas

    def _montar_tabela_medidas(self, lado):
        """Área e perímetro de cada parte; clicar num valor copia o número."""
        cores = self._cores
        tabela = ttk.Frame(lado)
        tabela.pack(anchor="w", fill="x")
        tabela.columnconfigure(1, weight=1, uniform="medida")
        tabela.columnconfigure(2, weight=1, uniform="medida")
        for coluna, texto in ((1, "Área"), (2, "Perímetro")):
            ttk.Label(tabela, text=texto, foreground=cores.texto_suave).grid(
                row=0, column=coluna, sticky="e", pady=(0, 2)
            )
        for linha, (camada, nome) in enumerate(
            (("externa", "Externa"), ("hall", "Hall")), start=1
        ):
            ttk.Label(tabela, text=nome, font=("Segoe UI", 9, "bold")).grid(
                row=linha, column=0, sticky="w", padx=(0, 12), pady=1
            )
            for coluna, tipo in ((1, "area"), (2, "perimetro")):
                var = tk.StringVar(value="—")
                self._vars_medidas[(camada, tipo)] = var
                valor = ttk.Label(
                    tabela,
                    textvariable=var,
                    font=("Segoe UI", 9, "bold"),
                    anchor="e",
                    cursor="hand2",
                )
                valor.grid(row=linha, column=coluna, sticky="e", pady=1)
                valor.bind(
                    "<Button-1>",
                    lambda _e, c=camada, t=tipo, n=nome: self._copiar_medida(c, t, n),
                )
                valor.bind(
                    "<Enter>", lambda _e, w=valor: w.configure(foreground=cores.titulo)
                )
                valor.bind("<Leave>", lambda _e, w=valor: w.configure(foreground=""))
                vincular_tooltip(
                    valor, lambda c=camada, t=tipo: self._dica_medida(c, t)
                )

    def _valor_medida(self, camada: str, tipo: str) -> float | None:
        res = self._resultados.get(camada)
        if res is None:
            return None
        if tipo == "area":
            return res.area_m2 if res.fechado else None
        return res.perimetro_m

    def _dica_medida(self, camada: str, tipo: str) -> str:
        if self._valor_medida(camada, tipo) is not None:
            return "Clique para copiar"
        res = self._resultados.get(camada)
        if tipo == "area" and res is not None and not res.fechado:
            return "Feche o desenho para calcular a área"
        return "Ainda não desenhado"

    def _copiar_medida(self, camada: str, tipo: str, nome: str):
        valor = self._valor_medida(camada, tipo)
        if valor is None:
            return
        texto = formatar_decimal_br(valor, 2)
        try:
            self.janela.clipboard_clear()
            self.janela.clipboard_append(texto)
        except tk.TclError:
            return
        medida = "área" if tipo == "area" else "perímetro"
        parte = "da externa" if camada == "externa" else "do hall"
        self._mostrar_feedback(f"Copiado: {texto} ({medida} {parte})")

    def _mostrar_feedback(self, texto: str):
        self.var_feedback.set(texto)
        if self._job_feedback is not None:
            try:
                self.janela.after_cancel(self._job_feedback)
            except tk.TclError:
                pass
        self._job_feedback = self.janela.after(
            4000, lambda: self.var_feedback.set("")
        )

    # ------------------------------------------------------------ arquivo

    def _montar_arquivo(self, lado):
        """Abrir e salvar desenhos (só no ORCCAD avulso)."""
        cores = self._cores
        estilos = estilos_botao(self.janela)
        ttk.Separator(lado).pack(fill="x", pady=(12, 8))
        botoes = ttk.Frame(lado)
        botoes.pack(fill="x")
        botoes.columnconfigure(0, weight=1, uniform="arquivo")
        botoes.columnconfigure(1, weight=1, uniform="arquivo")
        btn_abrir = criar_botao_ttk_com_icone(
            botoes,
            texto="Abrir desenho",
            nome_icone="folder-open-outline",
            command=self._abrir_arquivo,
            estilo=estilos.compacto,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        )
        btn_abrir.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        vincular_tooltip(btn_abrir, "Ctrl+O")
        btn_salvar = criar_botao_ttk_com_icone(
            botoes,
            texto="Salvar desenho",
            nome_icone="save-outline",
            command=self._salvar_arquivo,
            estilo=estilos.compacto,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        )
        btn_salvar.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        vincular_tooltip(btn_salvar, "Ctrl+S\nCtrl+Shift+S salva com outro nome")

        self.var_arquivo = tk.StringVar(value="")
        ttk.Label(
            lado,
            textvariable=self.var_arquivo,
            foreground=cores.texto_suave,
            wraplength=280,
        ).pack(anchor="w", pady=(6, 0))

        self.janela.bind("<Control-s>", lambda _e: self._salvar_arquivo() and None)
        self.janela.bind(
            "<Control-S>", lambda _e: self._salvar_arquivo(como=True) and None
        )
        self.janela.bind("<Control-o>", lambda _e: self._abrir_arquivo())

    def _tem_desenho(self) -> bool:
        return bool(self.painel.tem_pontos("externa") or self.painel.tem_pontos("hall"))

    def tem_alteracoes(self) -> bool:
        """Há algo desenhado que ainda não foi salvo em arquivo?"""
        if self.vinculado or not hasattr(self, "painel"):
            return False
        atual = self.painel.exportar()
        if self._caminho is None and not self._tem_desenho():
            return False
        return atual != self._desenho_salvo

    def _atualizar_titulo(self):
        titulo = "ORC — Desenho de metragens"
        if self._caminho is not None:
            titulo += f" — {self._caminho.name}"
        try:
            self.janela.title(titulo)
        except tk.TclError:
            pass

    def _atualizar_arquivo(self):
        if self.vinculado or not hasattr(self, "var_arquivo"):
            return
        if self._caminho is None:
            texto = "Desenho ainda não salvo" if self._tem_desenho() else ""
        elif self.tem_alteracoes():
            texto = f"{self._caminho.name} · alterações não salvas"
        else:
            texto = self._caminho.name
        if self.var_arquivo.get() != texto:
            self.var_arquivo.set(texto)

    def _salvar_arquivo(self, *, como: bool = False) -> bool:
        if not self._tem_desenho():
            messagebox.showinfo(
                "Salvar desenho", "Ainda não há nada desenhado.", parent=self.janela
            )
            return False
        caminho = None if como else self._caminho
        if caminho is None:
            escolhido = filedialog.asksaveasfilename(
                title="Salvar desenho",
                initialdir=str(self._caminho.parent if self._caminho else pasta_desenhos()),
                initialfile=self._caminho.name if self._caminho else "Planta" + EXTENSAO,
                defaultextension=EXTENSAO,
                filetypes=[("Desenho do ORCCAD", "*" + EXTENSAO)],
                parent=self.janela,
            )
            if not escolhido:
                return False
            caminho = Path(escolhido)
        desenho = self.painel.exportar()
        try:
            salvar_desenho(desenho, caminho)
        except OSError as exc:
            messagebox.showerror(
                "Salvar desenho",
                f"Não foi possível gravar o arquivo:\n{exc}",
                parent=self.janela,
            )
            return False
        self._caminho = caminho
        self._desenho_salvo = desenho
        self._atualizar_titulo()
        self._atualizar_arquivo()
        self._mostrar_feedback(f"Desenho salvo: {caminho.name}")
        return True

    def _abrir_arquivo(self):
        if not self._perguntar_salvar("Salvar o desenho atual antes de abrir outro?"):
            return
        escolhido = filedialog.askopenfilename(
            title="Abrir desenho",
            initialdir=str(self._caminho.parent if self._caminho else pasta_desenhos()),
            filetypes=[
                ("Desenho do ORCCAD", "*" + EXTENSAO),
                ("Todos os arquivos", "*.*"),
            ],
            parent=self.janela,
        )
        if not escolhido:
            return
        caminho = Path(escolhido)
        try:
            desenho = carregar_desenho(caminho)
        except DesenhoORCCADError as exc:
            messagebox.showerror("Abrir desenho", str(exc), parent=self.janela)
            return
        self.painel.carregar(desenho)
        self.painel._set_status("")
        self._caminho = caminho
        self._desenho_salvo = self.painel.exportar()
        self._atualizar_titulo()
        self._atualizar_arquivo()
        self._mostrar_feedback(f"Desenho aberto: {caminho.name}")
        try:
            self.painel.canvas.focus_set()
        except tk.TclError:
            pass

    def _perguntar_salvar(self, pergunta: str) -> bool:
        """Devolve False se o usuário desistiu (Cancelar ou não salvou)."""
        if not self.tem_alteracoes():
            return True
        try:
            self.trazer_frente()
        except tk.TclError:
            pass
        resposta = messagebox.askyesnocancel("ORCCAD", pergunta, parent=self.janela)
        if resposta is None:
            return False
        if resposta:
            return self._salvar_arquivo()
        return True

    def pode_fechar(self) -> bool:
        """Pergunta se quer salvar antes de fechar; False = não fechar."""
        try:
            if not self.janela.winfo_exists():
                return True
        except tk.TclError:
            return True
        return self._perguntar_salvar("Salvar o desenho antes de fechar?")

    def _ao_pedir_fechar(self):
        if self.pode_fechar():
            self._fechar()

    def _ao_resultado(self, resultados):
        if not isinstance(resultados, dict):
            resultados = {"externa": resultados, "hall": None}
        self._resultados = {
            "externa": resultados.get("externa"),
            "hall": resultados.get("hall"),
        }
        for (camada, tipo), var in self._vars_medidas.items():
            valor = self._valor_medida(camada, tipo)
            if valor is None:
                var.set("—")
            else:
                unidade = "m²" if tipo == "area" else "m"
                var.set(f"{formatar_decimal_br(valor, 2)} {unidade}")
        self._atualizar_arquivo()

        for chave, (var, tipo, camada) in self._vars_campos.items():
            texto = valor_para_campo(self._resultados.get(camada), tipo)
            if not texto:
                var.set("—")
                continue
            unidade = "m²" if tipo == "area" else "m"
            var.set(f"{texto} {unidade}")

    def _salvar_principal(self):
        if self.on_salvar_principal is None:
            return
        externa = self._resultados.get("externa")
        if externa is None or len(self.painel._camadas["externa"]["pontos"]) < 2:
            messagebox.showinfo(
                "Desenho",
                "Desenhe a parte EXTERNA da planta antes de salvar.",
                parent=self.janela,
            )
            return
        if not externa.fechado:
            messagebox.showinfo(
                "Desenho",
                "Complete o polígono da EXTERNA para obter área e perímetro.",
                parent=self.janela,
            )
            return
        valores = valores_campos_desenho(self._resultados)
        if not valores:
            messagebox.showinfo(
                "Desenho",
                "Não foi possível calcular as metragens deste desenho.",
                parent=self.janela,
            )
            return
        hall = self._resultados.get("hall")
        if hall is None or not hall.fechado:
            if not messagebox.askyesno(
                "Hall incompleto",
                "O HALL ainda não está completo.\n\n"
                "Salvar só com os campos da EXTERNA?\n"
                "(os 4 campos do hall não serão preenchidos)",
                parent=self.janela,
            ):
                return
        self.on_salvar_principal(self.painel.exportar(), valores)
        self._fechar()

    def _fechar(self):
        callback = self.on_fechar
        self.on_fechar = None
        try:
            self.painel._desvincular_atalhos()
        except tk.TclError:
            pass
        if callback:
            callback()
        try:
            if self.janela.winfo_exists():
                self.janela.destroy()
        except tk.TclError:
            pass

    def trazer_frente(self):
        try:
            self.janela.deiconify()
            self.janela.lift()
            self.janela.focus_force()
            self.painel.canvas.focus_set()
            self.painel.enquadrar_quando_visivel()
        except tk.TclError:
            pass
