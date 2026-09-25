"""Janela de desenho de metragens (ORCCAD) para a Área Comum."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.desenho_geometria import ResultadoDesenho
from ui.desenho_2d import (
    CAMPOS_DESENHO_AREA_COMUM,
    PainelDesenho2D,
    valor_para_campo,
)
from ui.temas import aplicar_chrome_dialogo, aplicar_tema, cores_tema
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    formatar_decimal_br,
    preparar_toplevel,
    vincular_tooltip,
)

CHAVE_AREA_PLANTA = "area_construida_m2"
CHAVE_PERIMETRO_FACHADA = "perimetro_paredes_externas_bloco_m"


class JanelaORCCAD:
    """Prévia autônoma ou diálogo ligado ao rascunho da Área Comum."""

    def __init__(
        self,
        parent,
        *,
        standalone: bool = False,
        on_salvar_principal=None,
        on_aplicar_campo=None,
        on_fechar=None,
        desenho_inicial=None,
    ):
        self.on_salvar_principal = on_salvar_principal
        self.on_aplicar_campo = on_aplicar_campo
        self.on_fechar = on_fechar
        self._resultado: ResultadoDesenho | None = None
        self._valores = {chave: "" for chave, _rotulo, _tipo in CAMPOS_DESENHO_AREA_COMUM}

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
        self.janela.title("ORC — Desenho de metragens")
        self.janela.minsize(1100, 680)
        self.janela.protocol("WM_DELETE_WINDOW", self._fechar)

        raiz = ttk.Frame(self.janela)
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)

        self.painel = PainelDesenho2D(raiz, on_resultado=self._ao_resultado)
        self.painel.grid(row=0, column=0, sticky="nsew")

        lado = ttk.Frame(raiz, padding=10)
        lado.grid(row=0, column=1, sticky="ns")
        raiz.columnconfigure(1, minsize=300)

        ttk.Label(
            lado,
            text="Medidas para cálculos",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            lado,
            text=(
                "Desenhe a planta do condomínio para obter as medidas para cálculos."
            ),
            wraplength=280,
        ).pack(anchor="w", pady=(4, 10))

        self.var_area = tk.StringVar(value="Área: —")
        self.var_perim = tk.StringVar(value="Perímetro: —")
        ttk.Label(lado, textvariable=self.var_area, font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        ttk.Label(lado, textvariable=self.var_perim, font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 12)
        )

        if self.on_salvar_principal is not None:
            btn_salvar = ttk.Button(
                lado,
                text="Salvar planta no orçamento",
                command=self._salvar_principal,
            )
            btn_salvar.pack(fill="x")
            vincular_tooltip(
                btn_salvar,
                "Grava a área construída e o perímetro das fachadas "
                "e mostra o desenho em Dados iniciais.",
            )

        ttk.Label(lado, text="Campo da Área Comum").pack(anchor="w", pady=(12, 0))
        self._rotulo_por_chave = {
            chave: rotulo for chave, rotulo, _tipo in CAMPOS_DESENHO_AREA_COMUM
        }
        self._tipo_por_chave = {
            chave: tipo for chave, _rotulo, tipo in CAMPOS_DESENHO_AREA_COMUM
        }
        self.var_campo = tk.StringVar(value=CAMPOS_DESENHO_AREA_COMUM[0][1])
        self.combo_campo = ttk.Combobox(
            lado,
            textvariable=self.var_campo,
            values=[rotulo for _chave, rotulo, _tipo in CAMPOS_DESENHO_AREA_COMUM],
            state="readonly",
            width=38,
        )
        self.combo_campo.pack(fill="x", pady=(2, 8))

        texto_usar = (
            "Usar metragem neste campo"
            if self.on_aplicar_campo is None
            else "Preencher este campo no orçamento"
        )
        btn_usar = ttk.Button(lado, text=texto_usar, command=self._aplicar_campo)
        btn_usar.pack(fill="x")
        vincular_tooltip(
            btn_usar,
            "Copia área ou perímetro do desenho para o campo escolhido.",
        )
        btn_copiar = ttk.Button(lado, text="Copiar valor", command=self._copiar_valor)
        btn_copiar.pack(fill="x", pady=(4, 8))
        vincular_tooltip(btn_copiar, "Copia o número para a área de transferência.")

        self.var_feedback = tk.StringVar(value="")
        ttk.Label(
            lado,
            textvariable=self.var_feedback,
            wraplength=280,
            foreground=cores.titulo,
        ).pack(anchor="w", pady=(0, 10))

        if self.on_aplicar_campo is None:
            ttk.Separator(lado).pack(fill="x", pady=4)
            ttk.Label(
                lado,
                text="Campos preenchidos (simulação)",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", pady=(6, 4))
            self._vars_campos = {}
            for chave, rotulo, _tipo in CAMPOS_DESENHO_AREA_COMUM:
                linha = ttk.Frame(lado)
                linha.pack(fill="x", pady=1)
                ttk.Label(linha, text=rotulo + ":", wraplength=190).pack(
                    side="left", anchor="w"
                )
                var = tk.StringVar(value="—")
                ttk.Label(linha, textvariable=var, width=10, anchor="e").pack(side="right")
                self._vars_campos[chave] = var
        else:
            self._vars_campos = {}

        self.painel.vincular_atalhos(self.janela)
        if not standalone:
            centralizar_janela(self.janela, parent, largura=1280, altura=760)
        if desenho_inicial:
            self.painel.carregar(desenho_inicial)
        self.janela.after_idle(lambda: self.painel.canvas.focus_set())
        self.janela.after_idle(self.painel.enquadrar_quando_visivel)
        self.janela.after(120, self.painel.enquadrar_quando_visivel)

    def _chave_campo(self) -> str:
        rotulo = self.var_campo.get()
        for chave, nome, _tipo in CAMPOS_DESENHO_AREA_COMUM:
            if nome == rotulo:
                return chave
        return CAMPOS_DESENHO_AREA_COMUM[0][0]

    def _ao_resultado(self, resultado: ResultadoDesenho | None):
        self._resultado = resultado
        if resultado is None:
            self.var_area.set("Área: —")
            self.var_perim.set("Perímetro: —")
            return
        if resultado.fechado:
            self.var_area.set(f"Área: {formatar_decimal_br(resultado.area_m2, 2)} m²")
        else:
            self.var_area.set("Área: — (complete o polígono)")
        self.var_perim.set(
            f"Perímetro: {formatar_decimal_br(resultado.perimetro_m, 2)} m"
        )

    def _aplicar_campo(self):
        chave = self._chave_campo()
        tipo = self._tipo_por_chave[chave]
        texto = valor_para_campo(self._resultado, tipo)
        if not texto:
            if tipo == "area":
                self.var_feedback.set("Complete o polígono para obter a área.")
            else:
                self.var_feedback.set("Desenhe pelo menos um segmento.")
            return
        self._valores[chave] = texto
        unidade = "m²" if tipo == "area" else "m"
        if chave in self._vars_campos:
            self._vars_campos[chave].set(f"{texto} {unidade}")
        if self.on_aplicar_campo is not None:
            self.on_aplicar_campo(chave, texto)
            self.var_feedback.set(
                f"Preenchido «{self._rotulo_por_chave[chave]}» com {texto} {unidade}."
            )
        else:
            self.var_feedback.set(
                f"Preencheria «{self._rotulo_por_chave[chave]}» com {texto} {unidade}."
            )

    def _salvar_principal(self):
        if self.on_salvar_principal is None:
            return
        resultado = self._resultado
        if resultado is None or len(self.painel.pontos) < 2:
            messagebox.showinfo(
                "Desenho",
                "Desenhe a planta do condomínio antes de salvar.",
                parent=self.janela,
            )
            return
        if not resultado.fechado:
            messagebox.showinfo(
                "Desenho",
                "Complete o polígono (Completar ou clique no primeiro ponto) "
                "para obter a área e o perímetro das fachadas.",
                parent=self.janela,
            )
            return
        area = valor_para_campo(resultado, "area")
        peri = valor_para_campo(resultado, "perimetro")
        if not area or not peri:
            messagebox.showinfo(
                "Desenho",
                "Não foi possível calcular área e perímetro deste polígono.",
                parent=self.janela,
            )
            return
        self.on_salvar_principal(
            self.painel.exportar(),
            {CHAVE_AREA_PLANTA: area, CHAVE_PERIMETRO_FACHADA: peri},
        )
        self._fechar()

    def _copiar_valor(self):
        chave = self._chave_campo()
        tipo = self._tipo_por_chave[chave]
        texto = valor_para_campo(self._resultado, tipo) or self._valores.get(chave, "")
        if not texto:
            self.var_feedback.set("Nada para copiar ainda.")
            return
        self.janela.clipboard_clear()
        self.janela.clipboard_append(texto)
        self.var_feedback.set(f"Copiado: {texto}")

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
