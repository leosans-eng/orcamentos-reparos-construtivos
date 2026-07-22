"""Verificação de atualização via version.json no GitHub (raw)."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import unquote, urlparse
from tkinter import messagebox, ttk

import certifi
import tkinter as tk

from ui.widgets import aplicar_icone_janela, centralizar_janela, preparar_toplevel

VERSION_JSON_URL = (
    "https://raw.githubusercontent.com/leosans-eng/"
    "orcamento-reparos-construtivos/main/version.json"
)
INSTALLER_FALLBACK_NAME = "ORC_Instalador.exe"
REQUEST_TIMEOUT_SEC = 60
CHUNK_SIZE = 256 * 1024
# Instalador PyInstaller+Inno costuma ter vários MB; evita reaproveitar .exe parcial.
MIN_INSTALLER_BYTES = 1_000_000
UI_POLL_MS = 100
PROGRESS_UI_INTERVAL_SEC = 0.25


def parse_version(value: str) -> tuple[int, ...]:
    text = str(value).strip().lstrip("vV")
    parts: list[int] = []
    for segment in text.split("."):
        segment = segment.split("-")[0].split("+")[0]
        if not segment:
            continue
        if not segment.isdigit():
            break
        parts.append(int(segment))
    return tuple(parts) if parts else (0,)


def is_remote_newer(remote_version: str, local_version: str) -> bool:
    return parse_version(remote_version) > parse_version(local_version)


def _read_version_field(payload: dict) -> str:
    """Aceita 'versao' (legado e padrão do ORC) ou 'version' (compat. com outros projetos)."""
    for key in ("versao", "version"):
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    return ""


def fetch_remote_version_info(
    app_version: str,
    url: str = VERSION_JSON_URL,
    timeout: int = REQUEST_TIMEOUT_SEC,
) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"ORC/{app_version}"},
    )
    with open_url(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        return None
    version = _read_version_field(payload)
    download = str(payload.get("download", "")).strip()
    if not version or not download:
        return None
    return {
        "version": version,
        "download": download,
    }


def format_download_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}: {exc.reason or 'erro no servidor'}"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            return (
                "Falha ao verificar certificado SSL do servidor. "
                "Reinstale a versão mais recente do programa ou verifique a conexão com a internet."
            )
        if reason is None:
            return "Falha de conexão com o servidor."
        if isinstance(reason, BaseException):
            text = str(reason).strip()
            return text if text and text.lower() != "none" else repr(reason)
        text = str(reason).strip()
        return text if text and text.lower() != "none" else "Falha de conexão com o servidor."
    if isinstance(exc, ssl.SSLCertVerificationError):
        return (
            "Falha ao verificar certificado SSL do servidor. "
            "Reinstale a versão mais recente do programa ou verifique a conexão com a internet."
        )
    text = str(exc).strip()
    if not text or text.lower() == "none":
        return repr(exc)
    return text


def download_folder() -> Path:
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    return Path(tempfile.gettempdir())


def resolve_download_destination(url: str) -> Path:
    filename = unquote(Path(urlparse(url).path).name)
    if not filename.lower().endswith(".exe"):
        filename = INSTALLER_FALLBACK_NAME
    return download_folder() / filename


def installer_parece_completo(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= MIN_INSTALLER_BYTES
    except OSError:
        return False


def create_ssl_context() -> ssl.SSLContext:
    """Usa certificados do certifi (incluso no .exe) para evitar falha de SSL em outros PCs."""
    ca_bundle = certifi.where()
    if Path(ca_bundle).is_file():
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def open_url(request: urllib.request.Request, timeout: int = REQUEST_TIMEOUT_SEC):
    context = create_ssl_context()
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def download_file(
    url: str,
    destination: Path,
    app_version: str,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    """Baixa para ``destination.part`` e renomeia ao concluir (mais seguro com antivírus)."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"ORC/{app_version}"},
    )
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        if partial.exists():
            partial.unlink()
    except OSError:
        pass

    with open_url(request) as response:
        total = int(response.headers.get("Content-Length", 0) or 0)
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            raise ValueError(
                "O link de download retornou uma página web em vez do instalador. "
                "Verifique a URL em version.json no GitHub."
            )
        downloaded = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

        if downloaded <= 0:
            raise OSError("O arquivo baixado está vazio.")
        if total > 0 and downloaded < total:
            raise OSError(
                f"Download incompleto ({downloaded} de {total} bytes). "
                "Tente novamente."
            )
        if downloaded < MIN_INSTALLER_BYTES:
            raise OSError(
                "O arquivo baixado é pequeno demais para ser o instalador. "
                "Verifique a conexão e tente novamente."
            )

    try:
        if destination.exists():
            destination.unlink()
    except OSError:
        pass
    partial.replace(destination)


class UpdateDialog(tk.Toplevel):
    def __init__(self, root: tk.Misc, info: dict, app_version: str):
        super().__init__(root)
        preparar_toplevel(self)
        self.root = root
        self.info = info
        self.app_version = app_version
        self.download_path: Path | None = None
        self._cancelled = False
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._last_progress_ui = 0.0

        remote_version = info["version"]
        self.title("Atualização disponível")
        aplicar_icone_janela(self)
        self.resizable(False, False)
        self.transient(root)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"Nova versão: {remote_version}",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=f"Versão instalada: {app_version}",
        ).pack(anchor="w", pady=(4, 12))

        self.status_var = tk.StringVar(value="Preparando download do instalador...")
        ttk.Label(frame, textvariable=self.status_var, wraplength=420).pack(
            anchor="w", pady=(0, 6)
        )

        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=420)
        self.progress.pack(fill="x", pady=(0, 12))
        self.progress.start(12)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        self.install_button = ttk.Button(
            buttons,
            text="Instalar agora",
            command=self.install_download,
            state="disabled",
        )
        self.install_button.pack(side="left", padx=(0, 6))
        self.retry_button = ttk.Button(
            buttons,
            text="Tentar novamente",
            command=self._retry_download,
            state="disabled",
        )
        self.retry_button.pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons, text="Abrir pasta", command=self.open_download_folder
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons,
            text="Depois",
            command=lambda: self.close_dialog(recusar=True),
        ).pack(side="right")

        self.protocol(
            "WM_DELETE_WINDOW",
            lambda: self.close_dialog(recusar=True),
        )
        self.update_idletasks()
        centralizar_janela(self, root)

        # Poll na thread da UI — nunca chamar after() a partir da thread de rede.
        self.after(UI_POLL_MS, self._processar_fila_ui)
        self.after(200, self.start_download)

    def close_dialog(self, *, recusar: bool = True) -> None:
        self._cancelled = True
        if recusar:
            marcar_atualizacao_adiada()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def _processar_fila_ui(self) -> None:
        if self._cancelled:
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                try:
                    callback()
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        try:
            if self.winfo_exists() and not self._cancelled:
                self.after(UI_POLL_MS, self._processar_fila_ui)
        except tk.TclError:
            pass

    def _agendar_ui(self, callback: Callable[[], None]) -> None:
        if self._cancelled:
            return
        self._ui_queue.put(callback)

    def start_download(self) -> None:
        destination = resolve_download_destination(self.info["download"])
        if installer_parece_completo(destination):
            self.download_path = destination
            self._on_download_success()
            return
        # Remove .exe incompleto / .part antigo para forçar download limpo.
        for candidato in (destination, destination.with_suffix(destination.suffix + ".part")):
            try:
                if candidato.is_file() and not installer_parece_completo(candidato):
                    candidato.unlink()
            except OSError:
                pass

        self.install_button.configure(state="disabled")
        self.retry_button.configure(state="disabled")
        self.status_var.set("Conectando ao servidor de download...")
        self.progress.stop()
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _retry_download(self) -> None:
        self.download_path = None
        self.start_download()

    def _download_worker(self) -> None:
        destination = resolve_download_destination(self.info["download"])
        try:
            self._agendar_ui(
                lambda: self.status_var.set("Baixando instalador...")
            )

            def on_progress(done: int, total: int) -> None:
                if self._cancelled:
                    return
                agora = time.monotonic()
                # Evita enfileirar milhares de updates; libera a fila da UI.
                if (
                    agora - self._last_progress_ui < PROGRESS_UI_INTERVAL_SEC
                    and total > 0
                    and done < total
                ):
                    return
                self._last_progress_ui = agora
                if total > 0:
                    percent = min(100, int(done * 100 / total))
                    text = f"Baixando instalador... {percent}%"
                    mode: Literal["determinate", "indeterminate"] = "determinate"
                    value = percent
                else:
                    mb = done / (1024 * 1024)
                    text = f"Baixando instalador... {mb:.1f} MB"
                    mode = "indeterminate"
                    value = 0
                self._agendar_ui(
                    lambda t=text, m=mode, v=value: self._update_progress(t, m, v)
                )

            download_file(
                self.info["download"],
                destination,
                self.app_version,
                on_progress=on_progress,
            )
            if self._cancelled:
                return
            if not installer_parece_completo(destination):
                raise OSError("O arquivo baixado está incompleto ou inválido.")
            self.download_path = destination
            self._agendar_ui(self._on_download_success)
        except Exception as exc:
            if not self._cancelled:
                message = format_download_error(exc)
                self._agendar_ui(lambda msg=message: self._on_download_error(msg))

    def _update_progress(
        self, text: str, mode: Literal["determinate", "indeterminate"], value: int
    ) -> None:
        if not self.winfo_exists():
            return
        self.status_var.set(text)
        self.progress.stop()
        self.progress.configure(mode=mode, maximum=100)
        if mode == "determinate":
            self.progress["value"] = value
        else:
            self.progress.start(12)

    def _on_download_success(self) -> None:
        if not self.winfo_exists():
            return
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        path = self.download_path
        self.status_var.set(f"Download concluído:\n{path}")
        self.install_button.configure(state="normal")
        self.retry_button.configure(state="disabled")
        messagebox.showinfo(
            "Atualização baixada",
            "O instalador foi baixado.\n\n"
            'Clique em "Ok" e depois em "Instalar agora" para atualizar.',
            parent=self,
        )

    def _on_download_error(self, message: str) -> None:
        if not self.winfo_exists():
            return
        self.progress.stop()
        self.status_var.set(f"Falha no download: {message}")
        self.retry_button.configure(state="normal")
        messagebox.showerror(
            "Erro no download",
            f"Não foi possível baixar a atualização.\n\n{message}\n\n"
            'Use "Tentar novamente" ou feche e abra o programa de novo.',
            parent=self,
        )

    def install_download(self) -> None:
        if not self.download_path or not self.download_path.exists():
            messagebox.showwarning(
                "Aviso", "Arquivo do instalador não encontrado.", parent=self
            )
            return
        try:
            os.startfile(self.download_path)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen([str(self.download_path)], shell=True)
        except OSError as exc:
            messagebox.showerror(
                "Erro", f"Não foi possível abrir o instalador:\n{exc}", parent=self
            )
            return
        parent = self.root
        self.close_dialog(recusar=False)
        try:
            if parent.winfo_exists():
                messagebox.showinfo(
                    "Instalação",
                    "O instalador foi aberto. Feche este programa antes de concluir a instalação.",
                    parent=parent,
                )
        except tk.TclError:
            pass

    def open_download_folder(self) -> None:
        folder = (
            self.download_path.parent
            if self.download_path
            else download_folder()
        )
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["xdg-open", str(folder)])


def check_for_updates(
    root: tk.Misc, app_version: str, *, url: str = VERSION_JSON_URL
) -> None:
    """Atalho: inicia (ou continua) a verificação amarrada a ``root``."""
    iniciar_verificacao_atualizacao(root, app_version, url=url)


def marcar_atualizacao_adiada() -> None:
    """Usuário clicou em Depois / fechou o diálogo — não oferecer de novo nesta sessão."""
    with _coordenador_lock:
        if _coordenador is not None:
            _coordenador.marcar_adiada()


def reiniciar_coordenador_atualizacao() -> None:
    """Cancela polls e limpa o parent ao destruir a janela (logout)."""
    with _coordenador_lock:
        if _coordenador is not None:
            _coordenador.desligar_ui()


def iniciar_verificacao_atualizacao(
    root: tk.Misc,
    app_version: str,
    *,
    url: str = VERSION_JSON_URL,
) -> None:
    """
    Inicia a busca de atualização (se ainda não começou) e registra ``root``
    como janela onde o diálogo deve aparecer.

    Pode ser chamado várias vezes (login, depois hub): a busca não se repete;
    se o usuário adiar (Depois), o aviso não volta até reiniciar o processo.
    """
    if os.environ.get("SKIP_UPDATE_CHECK", "").strip() in ("1", "true", "yes"):
        return

    global _coordenador
    with _coordenador_lock:
        if _coordenador is None or _coordenador.app_version != app_version:
            _coordenador = _UpdateCheckCoordinator(app_version, url=url)
        coordenador = _coordenador

    coordenador.registrar_janela(root)


class _UpdateCheckCoordinator:
    """
    Uma única busca em thread de rede.

    A abertura do diálogo é feita só via poll na thread da UI (`after`),
    porque Tk não permite `after`/`winfo_exists` chamados de outra thread.
    """

    _POLL_MS = 200
    _ATRASO_INICIAL_SEC = 1.5

    def __init__(self, app_version: str, *, url: str = VERSION_JSON_URL):
        self.app_version = app_version
        self.url = url
        self._lock = threading.Lock()
        self._parent: tk.Misc | None = None
        self._info: dict | None = None
        self._busca_iniciada = False
        self._busca_concluida = False
        self._adiada = False
        self._ja_oferecida = False
        self._dialogo: UpdateDialog | None = None
        self._poll_id: str | None = None
        self._poll_parent: tk.Misc | None = None

    def marcar_adiada(self) -> None:
        with self._lock:
            self._adiada = True
            self._ja_oferecida = True
            self._dialogo = None
        self._cancelar_poll()

    def desligar_ui(self) -> None:
        """Solta a janela atual sem descartar o resultado da busca."""
        self._cancelar_poll()
        with self._lock:
            self._parent = None
            self._dialogo = None

    def _cancelar_poll(self) -> None:
        poll_id = self._poll_id
        poll_parent = self._poll_parent
        self._poll_id = None
        self._poll_parent = None
        if poll_id is None or poll_parent is None:
            return
        try:
            poll_parent.after_cancel(poll_id)
        except (tk.TclError, ValueError):
            pass

    def _janela_viva(self, widget: tk.Misc | None) -> bool:
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _dialogo_esta_visivel(self) -> bool:
        return self._janela_viva(self._dialogo)

    def registrar_janela(self, parent: tk.Misc) -> None:
        with self._lock:
            self._parent = parent
            if self._adiada or self._ja_oferecida:
                return

        self._iniciar_busca_se_preciso()
        self._iniciar_poll(parent)

    def _iniciar_busca_se_preciso(self) -> None:
        with self._lock:
            if self._busca_iniciada:
                return
            self._busca_iniciada = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        time.sleep(self._ATRASO_INICIAL_SEC)
        info = None
        try:
            remoto = fetch_remote_version_info(self.app_version, self.url)
            if remoto and is_remote_newer(remoto["version"], self.app_version):
                info = remoto
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
            ValueError,
        ):
            info = None

        with self._lock:
            self._info = info
            self._busca_concluida = True

    def _iniciar_poll(self, parent: tk.Misc) -> None:
        self._cancelar_poll()

        if not self._janela_viva(parent):
            return

        self._poll_parent = parent

        def tick() -> None:
            self._poll_id = None
            try:
                if not self._janela_viva(parent):
                    return

                with self._lock:
                    if self._adiada or self._ja_oferecida:
                        return
                    alvo = self._parent
                    info = self._info
                    concluida = self._busca_concluida
                    dialogo_visivel = self._dialogo_esta_visivel()

                if alvo is not parent:
                    return

                if info is not None and not dialogo_visivel:
                    try:
                        dialogo = UpdateDialog(parent, info, self.app_version)
                        with self._lock:
                            self._dialogo = dialogo
                            self._ja_oferecida = True
                    except (tk.TclError, RuntimeError):
                        with self._lock:
                            self._dialogo = None
                    return

                if not concluida:
                    self._poll_id = parent.after(self._POLL_MS, tick)
            except (tk.TclError, RuntimeError):
                return

        try:
            self._poll_id = parent.after(self._POLL_MS, tick)
        except (tk.TclError, RuntimeError):
            self._poll_id = None
            self._poll_parent = None


_coordenador: _UpdateCheckCoordinator | None = None
_coordenador_lock = threading.Lock()
