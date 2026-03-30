# Project Guidelines

## Mandatory Skill Bootstrap
- For every conversation in this workspace, always load and apply `.github/skills/sirius-toolbox-architecture/SKILL.md` first.
- Treat `sirius-toolbox-architecture` as the required router skill before any analysis, code generation, refactor, debugging, or documentation update.
- When a request involves implementation details, follow router dispatch and then apply:
  - `.github/skills/sirius-toolbox-architecture-spec/SKILL.md`
  - `.github/skills/sirius-toolbox-build/SKILL.md` (for build/package/exe requests)
  - `.github/skills/sirius-toolbox-version-control/SKILL.md` (for git/commit/changelog/release requests)
  - `.github/skills/sirius-toolbox-governance/SKILL.md`
- Do not skip skill routing, even for small changes.

## Code Style
- Use Python 3.12+ and keep changes compatible with current project dependencies in pyproject.toml.
- Keep module responsibilities clear by folder boundary under src/sirius_toolbox; avoid cross-layer shortcuts.
- Prefer minimal, focused edits and preserve existing CLI/WebUI behavior unless a task explicitly requires changes.

## Architecture
- Main entry is main.py, which prepends src and delegates to sirius_toolbox.app.run.
- Task execution flows through sirius_toolbox.tasks (models/handlers/queue/scheduler).
- Collectors are split by source type:
  - browser collectors in src/sirius_toolbox/collectors/browser
  - map API collectors in src/sirius_toolbox/collectors/maps
- Storage is abstracted in src/sirius_toolbox/storage and persists task-scoped raw/curated data under data/raw and data/curated/tasks.
- Export logic belongs to src/sirius_toolbox/exporters.
- WebUI server logic belongs to src/sirius_toolbox/webui.

## Build and Test
- Create/activate a virtual environment first, then install deps from pyproject.toml.
- Typical run commands:
  - python main.py (defaults to WebUI)
  - python main.py webui --host 127.0.0.1 --port 8787
  - python main.py poi --provider gaode --keyword <kw> --city <city>
  - python main.py xhs --keyword <kw> --max-items <n>
- Typical test commands:
  - python -m pytest -q
  - python -m pytest tests/unit/test_webui_async_tasks.py tests/unit/test_webui_records.py

## Conventions
- Keep task outputs task-scoped:
  - curated: data/curated/tasks/<task_id>/
  - raw: data/raw/<source>/<task_id>/
- For Xiaohongshu collection, ensure Playwright Chromium is installed before first run:
  - playwright install chromium
- Respect provider-specific environment variables:
  - GAODE_API_KEY for gaode
  - BAIDU_API_KEY for baidu
  - SIRIUS_DATA_DIR to override data root
- Compliance is required: only implement or run collection flows for authorized and lawful scenarios.

## Reference Docs
- Product/usage guide: README.md
- Architecture overview: docs/architecture.md
- Skill router: .github/skills/sirius-toolbox-architecture/SKILL.md
- Architecture spec details: .github/skills/sirius-toolbox-architecture-spec/SKILL.md
- Governance and sync rules: .github/skills/sirius-toolbox-governance/SKILL.md
- Build and packaging rules: .github/skills/sirius-toolbox-build/SKILL.md
- Version control and release rules: .github/skills/sirius-toolbox-version-control/SKILL.md
