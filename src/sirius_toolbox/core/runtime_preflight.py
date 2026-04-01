from __future__ import annotations

import importlib.util
import os
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


def _ensure_playwright_browser_path() -> None:
    if os.getenv("PLAYWRIGHT_BROWSERS_PATH"):
        return

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(local_app_data) / "ms-playwright")
        return

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / ".cache" / "ms-playwright")


def _chromium_ready() -> tuple[bool, str]:
    _ensure_playwright_browser_path()

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
    _ensure_playwright_browser_path()

    try:
        import playwright.__main__ as playwright_main

        argv_backup = sys.argv[:]
        try:
            sys.argv = ["playwright", "install", "chromium"]
            playwright_main.main()
            return True
        except SystemExit as exc:
            if int(getattr(exc, "code", 1) or 0) == 0:
                return True
        finally:
            sys.argv = argv_backup
    except Exception:  # noqa: BLE001
        pass

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
