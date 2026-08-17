# Development (uv)

This project is managed with [uv](https://docs.astral.sh/uv/) (Astral).
Do not use raw `pip install` / manual `venv` workflows for day-to-day work.

## Prerequisites

- Install uv: https://docs.astral.sh/uv/getting-started/installation/
- Node.js 22+ (only for the React viewer under `web/`)

## Bootstrap

```bash
cd sceneify
uv python install
uv sync --all-extras
```

`uv` creates `.venv`, installs the package in editable mode, and respects
`uv.lock` + `.python-version` (currently 3.13).

## Everyday commands

```bash
uv sync --all-extras          # refresh env from lockfile
uv lock                       # regenerate lock after pyproject changes
uv add httpx                  # add a runtime dependency
uv add --group dev pytest     # add a dev dependency
uv add --optional mesh trimesh
uv run pytest
uv run ruff check .
uv run ruff format .
uv run python examples/workflows/world_edit_save.py
uv run sceneify list-demos
```

## Viewer frontend

```bash
cd web
npm ci
npm test
npm run build
```

The production build is written to `src/sceneify/_web` so the PyPI wheel contains a ready-to-use
viewer. Rebuild it after changing `web/src`.

Browser end-to-end tests use the bundled example and a real Python server:

```bash
cd web
npx playwright install chromium
npm run test:e2e
```

During viewer development:

```bash
# terminal 1
uv run python examples/basics/basic_scene.py

# terminal 2
cd web && npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8765`.

## CI expectations

GitHub Actions (`ci.yml`) runs:

- `uv sync --frozen --all-extras`
- `ruff check` + `ruff format --check`
- `pytest` on Python 3.12 and 3.13
- `npm ci` + `npm test` + `npm run build` for the viewer

Publishing to PyPI is handled by `release.yml` after CI passes on `main`,
or by `publish.yml` for a manual GitHub Release / `workflow_dispatch`.

## Publishing

Every successful CI run on `main` creates a GitHub Release and publishes to
PyPI. Versioning lives in `versioning.json`:

- `major` and `minor` are set by you.
- `patch` is incremented on each release, producing tags like `0.0.1`,
  `0.0.2`, … Change `major` / `minor` in the file when you want `1.2.N`.
- `userNotes` is your prose for the release. Leave it empty if you only
  want the commit list.
- `commits` is rewritten by CI with the non-merge commits since the
  previous tag.

Skip a push with `[skip release]` in the commit subject.

Manual path:

1. Edit `major` / `minor` / `userNotes` in `versioning.json` if needed.
2. Push to `main` (or run the **Release** workflow).
3. CI must pass; then `release.yml` tags `MAJOR.MINOR.PATCH`, updates
   `versioning.json` / `pyproject.toml`, creates the GitHub Release, and
   uploads to PyPI via Trusted Publishing.

One-time setup on [PyPI](https://pypi.org/manage/account/publishing/):

- Owner: `KlajdiBeqiraj`
- Repository: `sceneify`
- Workflow: `publish.yml`
- Environment: `pypi`

You can also run the workflow manually (`workflow_dispatch`). Use
**dry_run** to build artifacts without uploading.

Local fallback (personal account only):

```bash
cd web && npm ci && npm run build && cd ..
uv build
uv publish
```

Publish only from your personal account, never from an org you do not own.
