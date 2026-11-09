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
                "Desenhe a EXTERNA e o HALL (Offset ou do zero) "
                "para obter as medidas."
            ),
            wraplength=280,
        ).pack(anchor="w", pady=(4, 10))

        self.var_area_ext = tk.StringVar(value="Externa · Área: —")
        self.var_perim_ext = tk.StringVar(value="Externa · Perímetro: —")
        self.var_area_hall = tk.StringVar(value="Hall · Área: —")
        self.var_perim_hall = tk.StringVar(value="Hall · Perímetro: —")
        for var in (
            self.var_area_ext,
            self.var_perim_ext,
            self.var_area_hall,
            self.var_perim_hall,
        ):
            ttk.Label(lado, textvariable=var, font=("Segoe UI", 9, "bold")).pack(
                anchor="w"
            )

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

        self._vars_campos = {}
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
        self.janela.after_idle(lambda: self.painel.canvas.focus_set())
        self.janela.after_idle(self.painel.enquadrar_quando_visivel)
        self.janela.after(120, self.painel.enquadrar_quando_visivel)

    def _fmt_camada(self, res: ResultadoDesenho | None, prefixo: str):
        if res is None:
            return f"{prefixo} · Área: —", f"{prefixo} · Perímetro: —"
        if res.fechado:
            area = f"{prefixo} · Área: {formatar_decimal_br(res.area_m2, 2)} m²"
        else:
            area = f"{prefixo} · Área: — (complete)"
        peri = f"{prefixo} · Perímetro: {formatar_decimal_br(res.perimetro_m, 2)} m"
        return area, peri

    def _ao_resultado(self, resultados):
        if not isinstance(resultados, dict):
            resultados = {"externa": resultados, "hall": None}
        self._resultados = {
            "externa": resultados.get("externa"),
            "hall": resultados.get("hall"),
        }
        ae, pe = self._fmt_camada(self._resultados["externa"], "Externa")
        ah, ph = self._fmt_camada(self._resultados["hall"], "Hall")
        self.var_area_ext.set(ae)
        self.var_perim_ext.set(pe)
        self.var_area_hall.set(ah)
        self.var_perim_hall.set(ph)

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
