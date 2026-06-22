"""Lê APP_VERSION de core/app_state.py (uso no build do instalador)."""

import re
import sys
from pathlib import Path

APP_STATE_FILE = Path(__file__).resolve().parents[1] / "core" / "app_state.py"


def read_app_version() -> str:
    text = APP_STATE_FILE.read_text(encoding="utf-8")
    match = re.search(
        r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE
    )
    if not match:
        raise SystemExit(f"APP_VERSION não encontrado em {APP_STATE_FILE}")
    return match.group(1)


if __name__ == "__main__":
    sys.stdout.write(read_app_version())
