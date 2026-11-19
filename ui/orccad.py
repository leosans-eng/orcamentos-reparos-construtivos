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
    parse_decimal_br,
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
        nome_planta: str = "",
        com_hall: bool = True,
    ):
        self.on_salvar_principal = on_salvar_principal
        self.on_fechar = on_fechar
        # Na Área Comum, cada estrutura tem a própria planta (nome_planta);
        # outras edificações (salão, guarita...) não têm hall.
        self.nome_planta = str(nome_planta or "").strip()
        self.com_hall = bool(com_hall)
        # Aberto pela Área Comum, o desenho alimenta o orçamento; aberto pelo
        # Hub, serve só para medir a planta e pode ser salvo em arquivo.
        self.vinculado = on_salvar_principal is not None
        self._caminho: Path | None = None
        self._desenho_salvo: dict | None = None
        self._job_feedback = None
        self._refs_icones: list = []
        self._vars_medidas: dict[tuple[str, str], tk.StringVar] = {}
        self._tabela = None
        self._linhas_comodos: list = []  # widgets das linhas de cômodos
        self._assinatura_comodos = None
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

        self.painel = PainelDesenho2D(
            raiz,
            on_resultado=self._ao_resultado,
            paredes=not self.vinculado,
            hall=self.com_hall,
        )
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
        if self.nome_planta:
            ttk.Label(
                lado,
                text=f"Planta: {self.nome_planta}",
                foreground=cores.titulo,
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", pady=(2, 10))
        elif not vinculado:
            ttk.Label(
                lado,
                text="Desenhe a planta para ver a área e o perímetro.",
                wraplength=280,
            ).pack(anchor="w", pady=(4, 10))
        else:
            ttk.Frame(lado, height=10).pack(anchor="w")

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
        self._desenho_aberto = self._desenho_salvo
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

        camada_atual = None
        for chave, rotulo, tipo, camada in CAMPOS_DESENHO_AREA_COMUM:
            if camada == "hall" and not self.com_hall:
                continue
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
        self._tabela = tabela
        tabela.columnconfigure(1, weight=1, uniform="medida")
        tabela.columnconfigure(2, weight=1, uniform="medida")
        for coluna, texto in ((1, "Área"), (2, "Perímetro")):
            ttk.Label(tabela, text=texto, foreground=cores.texto_suave).grid(
                row=0, column=coluna, sticky="e", pady=(0, 2)
            )
        camadas = [("externa", "Externa")] + ([("hall", "Hall")] if self.com_hall else [])
        for linha, (camada, nome) in enumerate(camadas, start=1):
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

    def _copiar_valor(self, valor: float, descricao: str):
        texto = formatar_decimal_br(valor, 2)
        try:
            self.janela.clipboard_clear()
            self.janela.clipboard_append(texto)
        except tk.TclError:
            return
        self._mostrar_feedback(f"Copiado: {texto} ({descricao})")

    # ------------------------------------------------------------ cômodos

    def _atualizar_comodos(self):
        """Linhas de cômodos na mesma grade da tabela de medidas."""
        if self._tabela is None or self.vinculado:
            return
        comodos = self.painel.comodos()
        tem_paredes = self.painel.tem_paredes()
        espessura = self.painel.espessura_paredes
        assinatura = (
            tem_paredes,
            espessura,
            tuple(
                (c.nome, round(c.area_exibida, 4), round(c.perimetro_exibido, 4))
                for c in comodos
            ),
        )
        if assinatura == self._assinatura_comodos:
            return
        self._assinatura_comodos = assinatura
        for widget in self._linhas_comodos:
            widget.destroy()
        self._linhas_comodos = []
        self.painel.destacar_comodo(None)
        if not tem_paredes:
            return

        cores = self._cores
        tabela = self._tabela
        linha = 3
        separador = ttk.Separator(tabela)
        separador.grid(row=linha, column=0, columnspan=3, sticky="ew", pady=(10, 6))
        self._linhas_comodos.append(separador)
        linha += 1

        # Espessura das paredes (0 = medidas pelo eixo das paredes).
        rotulo_esp = ttk.Label(tabela, text="Espessura das paredes")
        rotulo_esp.grid(row=linha, column=0, sticky="w", padx=(0, 12), pady=(0, 6))
        quadro_esp = ttk.Frame(tabela)
        quadro_esp.grid(row=linha, column=1, columnspan=2, sticky="e", pady=(0, 6))
        var_esp = tk.StringVar(value=formatar_decimal_br(espessura * 100, 1))
        entrada_esp = ttk.Entry(quadro_esp, textvariable=var_esp, width=5, justify="right")
        entrada_esp.pack(side="left")
        ttk.Label(quadro_esp, text=" cm").pack(side="left")
        vincular_tooltip(
            entrada_esp,
            "Desconta as paredes das medidas dos cômodos.\n"
            "A linha Externa é a face de fora: a parede fica toda para dentro.\n"
            "Paredes internas são o eixo: metade para cada lado.\n"
            "0 = medidas pelo eixo.",
        )
        entrada_esp.bind("<Return>", lambda _e: self._aplicar_espessura(var_esp))
        entrada_esp.bind("<KP_Enter>", lambda _e: self._aplicar_espessura(var_esp))
        entrada_esp.bind("<FocusOut>", lambda _e: self._aplicar_espessura(var_esp))
        self._linhas_comodos += [rotulo_esp, quadro_esp]
        linha += 1

        titulo = ttk.Label(tabela, text="Cômodos", font=("Segoe UI", 9, "bold"))
        titulo.grid(row=linha, column=0, sticky="w", pady=(0, 2))
        self._linhas_comodos.append(titulo)
        if espessura > 0:
            for coluna, texto in ((1, "Área útil"), (2, "Perím. útil")):
                cabecalho = ttk.Label(tabela, text=texto, foreground=cores.texto_suave)
                cabecalho.grid(row=linha, column=coluna, sticky="e", pady=(0, 2))
                self._linhas_comodos.append(cabecalho)
        linha += 1

        if not comodos:
            aviso = ttk.Label(
                tabela, text="Nenhum cômodo fechado", foreground=cores.texto_suave
            )
            aviso.grid(row=linha, column=0, columnspan=3, sticky="w")
            self._linhas_comodos.append(aviso)
            return

        sufixo = " útil" if espessura > 0 else ""
        for indice, comodo in enumerate(comodos):
            nome = ttk.Label(tabela, text=comodo.nome, cursor="xterm")
            nome.grid(row=linha, column=0, sticky="w", padx=(0, 12), pady=1)
            nome.bind(
                "<Double-Button-1>",
                lambda _e, i=indice, w=nome: self._editar_nome_comodo(i, w),
            )
            vincular_tooltip(nome, "Clique duas vezes para dar um nome")
            celulas = [nome]
            for coluna, valor, unidade, medida in (
                (1, comodo.area_exibida, "m²", "área" + sufixo),
                (2, comodo.perimetro_exibido, "m", "perímetro" + sufixo),
            ):
                celula = self._celula_copiavel(
                    tabela,
                    f"{formatar_decimal_br(valor, 2)} {unidade}",
                    valor,
                    f"{medida} de {comodo.nome}",
                    bold=False,
                )
                celula.grid(row=linha, column=coluna, sticky="e", pady=1)
                celulas.append(celula)
            for celula in celulas:
                celula.bind(
                    "<Enter>",
                    lambda _e, i=indice: self.painel.destacar_comodo(i),
                    add="+",
                )
                celula.bind(
                    "<Leave>", lambda _e: self.painel.destacar_comodo(None), add="+"
                )
            self._linhas_comodos += celulas
            linha += 1

        total_area = sum(c.area_exibida for c in comodos)
        total_perim = sum(c.perimetro_exibido for c in comodos)
        rotulo_total = ttk.Label(tabela, text="Total", font=("Segoe UI", 9, "bold"))
        rotulo_total.grid(row=linha, column=0, sticky="w", pady=(4, 0))
        self._linhas_comodos.append(rotulo_total)
        for coluna, valor, unidade, medida in (
            (1, total_area, "m²", f"área{sufixo} total dos cômodos"),
            (2, total_perim, "m", f"soma dos perímetros{sufixo} dos cômodos"),
        ):
            celula = self._celula_copiavel(
                tabela, f"{formatar_decimal_br(valor, 2)} {unidade}", valor, medida
            )
            celula.grid(row=linha, column=coluna, sticky="e", pady=(4, 0))
            self._linhas_comodos.append(celula)

    def _aplicar_espessura(self, var: tk.StringVar):
        texto = var.get().strip() or "0"
        try:
            cm = parse_decimal_br(texto)
        except ValueError:
            cm = -1
        if cm < 0 or cm > 100:
            var.set(formatar_decimal_br(self.painel.espessura_paredes * 100, 1))
            self._mostrar_feedback("Espessura inválida: use de 0 a 100 cm.")
            return "break"
        self.painel.definir_espessura(cm / 100.0)
        return "break"

    def _editar_nome_comodo(self, indice: int, rotulo: ttk.Label):
        """Troca o nome na tabela por um campo de texto (Enter confirma)."""
        info = rotulo.grid_info()
        var = tk.StringVar(value=rotulo.cget("text"))
        entrada = ttk.Entry(self._tabela, textvariable=var, width=16)
        entrada.grid(
            row=info["row"], column=0, sticky="we", padx=(0, 12), pady=1
        )
        entrada.focus_set()
        entrada.select_range(0, "end")
        terminou = False

        def aplicar(_e=None):
            nonlocal terminou
            if terminou:
                return "break"
            terminou = True
            texto = var.get()
            entrada.destroy()
            self.painel.renomear_comodo(indice, texto)
            return "break"

        def cancelar(_e=None):
            nonlocal terminou
            terminou = True
            entrada.destroy()
            return "break"

        entrada.bind("<Return>", aplicar)
        entrada.bind("<KP_Enter>", aplicar)
        entrada.bind("<Escape>", cancelar)
        entrada.bind("<FocusOut>", aplicar)
        self._linhas_comodos.append(entrada)

    def _celula_copiavel(self, parent, texto, valor, descricao, *, bold=True):
        cores = self._cores
        celula = ttk.Label(
            parent,
            text=texto,
            font=("Segoe UI", 9, "bold" if bold else "normal"),
            anchor="e",
            cursor="hand2",
        )
        celula.bind("<Button-1>", lambda _e: self._copiar_valor(valor, descricao))
        celula.bind(
            "<Enter>", lambda _e: celula.configure(foreground=cores.titulo), add="+"
        )
        celula.bind("<Leave>", lambda _e: celula.configure(foreground=""), add="+")
        vincular_tooltip(celula, "Clique para copiar")
        return celula

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
        return self.painel.tem_desenho()

    def alterado_desde_abertura(self) -> bool:
        """O desenho mudou desde que a janela abriu (ou desde a última gravação)?"""
        try:
            return self.painel.exportar() != self._desenho_aberto
        except tk.TclError:
            return False

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
        if self.nome_planta:
            titulo += f" · {self.nome_planta}"
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
        self._atualizar_comodos()

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
        if self.com_hall and (hall is None or not hall.fechado):
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
