from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

from sirius_toolbox.settings import Settings


REQUIRED_MODULES = [
    "httpx",
    "openpyxl",
    "PIL",
    "playwright",
    "pydantic",
    "tenacity",
]


def _missing_modules() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _chromium_ready() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return False, f"playwright import failed: {exc}"

    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            if executable.exists():
                return True, str(executable)
            return False, f"chromium executable missing: {executable}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _install_chromium() -> bool:
    commands: list[list[str]] = []

    if not getattr(sys, "frozen", False):
        commands.append([sys.executable, "-m", "playwright", "install", "chromium"])

    commands.extend(
        [
            ["playwright", "install", "chromium"],
            ["playwright.cmd", "install", "chromium"],
        ]
    )

    for cmd in commands:
        try:
            subprocess.run(cmd, check=True)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def ensure_runtime_ready(settings: Settings, *, require_chromium: bool) -> None:
    missing = _missing_modules()
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Runtime dependencies missing: {names}. "
            "Please reinstall package or use bootstrap script."
        )

    if not require_chromium:
        return

    ready, reason = _chromium_ready()
    if ready:
        return

    if settings.auto_install_chromium and _install_chromium():
        ready, reason = _chromium_ready()
        if ready:
            return

    raise RuntimeError(
        "Chromium runtime is not ready. "
        f"Reason: {reason}. "
        "Please run: playwright install chromium"
    )
