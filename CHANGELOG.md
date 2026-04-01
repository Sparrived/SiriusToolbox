# Changelog

## 2026-04-01

- feat(runtime): embed startup preflight into app entry to validate dependencies and Chromium before launching app body
- fix(bootstrap): detect missing Python packages before startup and install only when needed
- build(release): include one-click `start-webui.bat` in release assets and zip package
- feat(bootstrap): add one-click Windows startup flow via `start-webui.bat` and `scripts/bootstrap-webui.ps1` to auto-install Python 3.12, create virtual environment, install dependencies, install Chromium runtime, and launch WebUI

## 2026-03-30

- chore(repo): bootstrap SiriusToolbox initial codebase, skills, build/release workflow, and WebUI/task pipeline updates
