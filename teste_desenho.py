import tkinter as tk
from tkinter import ttk, messagebox
import math


class Desenho2D:
    def __init__(self, root):
        self.root = root
        self.root.title("Desenho 2D - Área e Perímetro")
        self.root.geometry("1000x700")

        # ---------------------------------------------------------
        # CONFIGURAÇÕES
        # ---------------------------------------------------------

        # Quantos metros reais correspondem a 1 pixel.
        # Exemplo:
        # 0.01 = 1 pixel representa 1 cm
        # 0.05 = 1 pixel representa 5 cm
        self.escala = 0.01

        # Pontos reais do desenho.
        # São armazenados em coordenadas do Canvas inicialmente.
        self.pontos = []

        # Linhas desenhadas no Canvas
        self.linhas = []

        # Textos das cotas
        self.cotas = []

        # Linha temporária que acompanha o mouse
        self.linha_temporaria = None

        # Texto temporário da medida
        self.cota_temporaria = None

        # Estado
        self.desenhando = False
        self.fechado = False

        # ---------------------------------------------------------
        # INTERFACE
        # ---------------------------------------------------------

        self.criar_interface()

        # Eventos do mouse
        self.canvas.bind("<Button-1>", self.clique_canvas)
        self.canvas.bind("<Motion>", self.mover_mouse)
        self.canvas.bind("<Button-3>", self.finalizar_desenho)

        # ESC cancela linha temporária
        self.root.bind("<Escape>", self.cancelar_linha)

    # =============================================================
    # INTERFACE
    # =============================================================

    def criar_interface(self):

        # -----------------------------
        # Barra superior
        # -----------------------------

        frame_topo = ttk.Frame(self.root, padding=8)
        frame_topo.pack(fill="x")

        ttk.Label(
            frame_topo,
            text="Escala (m/pixel):"
        ).pack(side="left")

        self.entrada_escala = ttk.Entry(
            frame_topo,
            width=10
        )
        self.entrada_escala.insert(0, "0.01")
        self.entrada_escala.pack(side="left", padx=(5, 15))

        ttk.Button(
            frame_topo,
            text="Aplicar escala",
            command=self.aplicar_escala
        ).pack(side="left")

        ttk.Button(
            frame_topo,
            text="Fechar polígono",
            command=self.fechar_poligono
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_topo,
            text="Novo desenho",
            command=self.novo_desenho
        ).pack(side="left", padx=5)

        # -----------------------------
        # Área de desenho
        # -----------------------------

        frame_canvas = ttk.Frame(self.root)
        frame_canvas.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5
        )

        self.canvas = tk.Canvas(
            frame_canvas,
            bg="white",
            highlightthickness=1,
            highlightbackground="#999999"
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

        # -----------------------------
        # Barra inferior
        # -----------------------------

        frame_resultado = ttk.Frame(
            self.root,
            padding=10
        )
        frame_resultado.pack(fill="x")

        self.label_area = ttk.Label(
            frame_resultado,
            text="Área: 0,00 m²",
            font=("Arial", 12, "bold")
        )

        self.label_area.pack(side="left", padx=20)

        self.label_perimetro = ttk.Label(
            frame_resultado,
            text="Perímetro: 0,00 m",
            font=("Arial", 12, "bold")
        )

        self.label_perimetro.pack(side="left", padx=20)

        self.label_status = ttk.Label(
            frame_resultado,
            text="Clique no Canvas para começar.",
            foreground="#444444"
        )

        self.label_status.pack(side="right", padx=20)

    # =============================================================
    # ESCALA
    # =============================================================

    def aplicar_escala(self):
        try:
            valor = float(
                self.entrada_escala.get().replace(",", ".")
            )

            if valor <= 0:
                raise ValueError

            self.escala = valor

            # Redesenha as cotas
            self.redesenhar()

        except ValueError:
            messagebox.showerror(
                "Erro",
                "Informe uma escala válida.\n\n"
                "Exemplo: 0.01"
            )

    # =============================================================
    # CLIQUE DO MOUSE
    # =============================================================

    def clique_canvas(self, event):

        if self.fechado:
            return

        x = event.x
        y = event.y

        # Primeiro ponto
        if not self.pontos:

            self.pontos.append((x, y))

            self.canvas.create_oval(
                x - 4,
                y - 4,
                x + 4,
                y + 4,
                fill="red",
                outline="red",
                tags="ponto"
            )

            self.desenhando = True

            self.label_status.config(
                text="Clique para criar o próximo ponto."
            )

            return

        # Segundo ponto em diante
        ultimo_x, ultimo_y = self.pontos[-1]

        # Adiciona novo ponto
        self.pontos.append((x, y))

        # Desenha o ponto
        self.canvas.create_oval(
            x - 4,
            y - 4,
            x + 4,
            y + 4,
            fill="red",
            outline="red",
            tags="ponto"
        )

        # Desenha segmento
        self.desenhar_segmento(
            ultimo_x,
            ultimo_y,
            x,
            y
        )

        # Remove linha temporária
        self.remover_temporario()

        self.label_status.config(
            text="Clique para continuar, botão direito ou 'Fechar polígono'."
        )

    # =============================================================
    # DESENHAR SEGMENTO
    # =============================================================

    def desenhar_segmento(
        self,
        x1,
        y1,
        x2,
        y2
    ):

        # Linha
        linha = self.canvas.create_line(
            x1,
            y1,
            x2,
            y2,
            fill="#1565C0",
            width=3
        )

        self.linhas.append(linha)

        # Comprimento em pixels
        distancia_px = math.hypot(
            x2 - x1,
            y2 - y1
        )

        # Comprimento real
        distancia_real = distancia_px * self.escala

        # Meio da linha
        xm = (x1 + x2) / 2
        ym = (y1 + y2) / 2

        # Pequeno deslocamento para a cota
        dx = x2 - x1
        dy = y2 - y1

        comprimento = math.hypot(dx, dy)

        if comprimento != 0:
            nx = -dy / comprimento
            ny = dx / comprimento
        else:
            nx = 0
            ny = 0

        deslocamento = 15

        texto_x = xm + nx * deslocamento
        texto_y = ym + ny * deslocamento

        # Texto da cota
        texto = self.canvas.create_text(
            texto_x,
            texto_y,
            text=f"{distancia_real:.2f} m",
            fill="#D32F2F",
            font=("Arial", 10, "bold"),
            tags="cota"
        )

        self.cotas.append(texto)

    # =============================================================
    # MOVIMENTO DO MOUSE
    # =============================================================

    def mover_mouse(self, event):

        if not self.pontos or self.fechado:
            return

        x = event.x
        y = event.y

        ultimo_x, ultimo_y = self.pontos[-1]

        self.remover_temporario()

        # Linha temporária
        self.linha_temporaria = self.canvas.create_line(
            ultimo_x,
            ultimo_y,
            x,
            y,
            fill="#999999",
            width=2,
            dash=(5, 5)
        )

        distancia_px = math.hypot(
            x - ultimo_x,
            y - ultimo_y
        )

        distancia_real = distancia_px * self.escala

        xm = (ultimo_x + x) / 2
        ym = (ultimo_y + y) / 2

        self.cota_temporaria = self.canvas.create_text(
            xm,
            ym - 15,
            text=f"{distancia_real:.2f} m",
            fill="#777777",
            font=("Arial", 9)
        )

    # =============================================================
    # REMOVER TEMPORÁRIO
    # =============================================================

    def remover_temporario(self):

        if self.linha_temporaria is not None:
            self.canvas.delete(
                self.linha_temporaria
            )
            self.linha_temporaria = None

        if self.cota_temporaria is not None:
            self.canvas.delete(
                self.cota_temporaria
            )
            self.cota_temporaria = None

    # =============================================================
    # CANCELAR LINHA
    # =============================================================

    def cancelar_linha(self, event=None):

        self.remover_temporario()

        self.label_status.config(
            text="Linha temporária cancelada."
        )

    # =============================================================
    # FINALIZAR DESENHO (BOTÃO DIREITO)
    # =============================================================

    def finalizar_desenho(self, event=None):
        """Fecha o polígono e calcula área/perímetro (bind do Button-3)."""
        self.fechar_poligono()

    # =============================================================
    # FECHAR POLÍGONO
    # =============================================================

    def fechar_poligono(self):

        if len(self.pontos) < 3:
            messagebox.showwarning(
                "Atenção",
                "É necessário ter pelo menos 3 pontos."
            )
            return

        if self.fechado:
            return

        primeiro_x, primeiro_y = self.pontos[0]
        ultimo_x, ultimo_y = self.pontos[-1]

        # Desenha último segmento
        self.desenhar_segmento(
            ultimo_x,
            ultimo_y,
            primeiro_x,
            primeiro_y
        )

        self.fechado = True
        self.desenhando = False

        self.remover_temporario()

        # Calcula resultados
        self.calcular_resultados()

        self.label_status.config(
            text="Polígono fechado."
        )

    # =============================================================
    # CÁLCULO DA ÁREA E PERÍMETRO
    # =============================================================

    def calcular_resultados(self):

        if len(self.pontos) < 3:
            return

        # ---------------------------------------------------------
        # PERÍMETRO
        # ---------------------------------------------------------

        perimetro_px = 0

        for i in range(len(self.pontos)):

            x1, y1 = self.pontos[i]

            x2, y2 = self.pontos[
                (i + 1) % len(self.pontos)
            ]

            distancia = math.hypot(
                x2 - x1,
                y2 - y1
            )

            perimetro_px += distancia

        perimetro = perimetro_px * self.escala

        # ---------------------------------------------------------
        # ÁREA - MÉTODO DE SHOELACE
        # ---------------------------------------------------------

        soma = 0

        for i in range(len(self.pontos)):

            x1, y1 = self.pontos[i]

            x2, y2 = self.pontos[
                (i + 1) % len(self.pontos)
            ]

            soma += (
                x1 * y2 -
                x2 * y1
            )

        area_px = abs(soma) / 2

        # Como escala é metros/pixel,
        # área precisa ser multiplicada pela escala ao quadrado.
        area = area_px * (self.escala ** 2)

        # Atualiza interface
        self.label_area.config(
            text=f"Área: {area:.2f} m²"
        )

        self.label_perimetro.config(
            text=f"Perímetro: {perimetro:.2f} m"
        )

    # =============================================================
    # NOVO DESENHO
    # =============================================================

    def novo_desenho(self):

        self.pontos.clear()
        self.linhas.clear()
        self.cotas.clear()

        self.fechado = False
        self.desenhando = False

        self.remover_temporario()

        self.canvas.delete("all")

        self.label_area.config(
            text="Área: 0,00 m²"
        )

        self.label_perimetro.config(
            text="Perímetro: 0,00 m"
        )

        self.label_status.config(
            text="Clique no Canvas para começar."
        )

    # =============================================================
    # REDESENHAR
    # =============================================================

    def redesenhar(self):

        if not self.pontos:
            return

        # Guarda os pontos
        pontos = self.pontos.copy()

        self.canvas.delete("all")

        self.linhas.clear()
        self.cotas.clear()

        # Redesenha pontos
        for x, y in pontos:

            self.canvas.create_oval(
                x - 4,
                y - 4,
                x + 4,
                y + 4,
                fill="red",
                outline="red",
                tags="ponto"
            )

        # Redesenha segmentos
        quantidade = len(pontos)

        for i in range(quantidade - 1):

            x1, y1 = pontos[i]
            x2, y2 = pontos[i + 1]

            self.desenhar_segmento(
                x1,
                y1,
                x2,
                y2
            )

        # Se estiver fechado, redesenha o último segmento
        if self.fechado:

            x1, y1 = pontos[-1]
            x2, y2 = pontos[0]

            self.desenhar_segmento(
                x1,
                y1,
                x2,
                y2
            )

            self.calcular_resultados()


# =============================================================
# PROGRAMA PRINCIPAL
# =============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = Desenho2D(root)

    root.mainloop()