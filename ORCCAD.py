#Prévia do desenho de metragens para o módulo Área Comum.


from __future__ import annotations

import tkinter as tk

from ui.orccad import JanelaORCCAD
from ui.widgets import aplicar_icone_janela, centralizar_janela


def main():
    root = tk.Tk()
    root.withdraw()
    aplicar_icone_janela(root)
    JanelaORCCAD(root, standalone=True)
    centralizar_janela(root, largura=1280, altura=760)
    root.mainloop()


if __name__ == "__main__":
    main()
