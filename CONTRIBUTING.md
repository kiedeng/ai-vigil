# Contributing to AI Vigil

Thanks for helping improve AI Vigil. This project welcomes bug reports, feature ideas, documentation fixes, tests, and code contributions.

## Development Setup

```bash
git clone https://github.com/kiedeng/ai-vigil.git
cd ai-vigil
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Frontend:

```bash
cd frontend
npm install
```

## Run Locally

Backend:

```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8010
```

Frontend:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Checks Before Pull Request

Run backend tests:

```bash
python -m pytest -p no:cacheprovider tests/backend
```

Run frontend build:

```bash
cd frontend
npm run build
```

## Pull Request Guidelines

- Keep changes focused and explain the motivation.
- Add or update tests for behavior changes.
- Update README or docs for user-facing changes.
- Do not commit `.env`, databases, logs, virtual environments, or build output.
- For schema changes, add an Alembic migration.

## Good First Issues

- Add new examples for model check configs.
- Improve dashboard empty states.
- Add notification adapters.
- Add tests around migration and alert behavior.
- Improve Docker deployment docs.
