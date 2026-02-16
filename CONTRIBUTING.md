# Contributing to RepoScan Pro

## Getting Started

1. Fork and clone the repository
2. Follow the [Local Development Guide](docs/LOCAL_DEV.md) to set up your environment
3. Create a feature branch from `main`

## Development Workflow

```bash
# Create a branch
git checkout -b feature/my-feature

# Make changes, then run checks
cd frontend && npm run lint && npm test
cd ../backend && ruff check . && pytest

# Commit and push
git add -A && git commit -m "feat: description of change"
git push -u origin feature/my-feature
```

## Code Standards

### Frontend (TypeScript/React)
- ESLint flat config (`eslint.config.js`) enforces rules automatically
- Run `npm run lint` before committing
- Write tests in Vitest for new components and utilities
- Use the `@/` path alias for imports

### Backend (Python/FastAPI)
- **Ruff** for linting and formatting (configured in `ruff.toml`)
- Run `ruff check .` and `ruff format --check .`
- Write pytest tests for new endpoints and services
- Use async patterns consistently (SQLAlchemy async sessions)

### Commit Messages
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat:` new feature
  - `fix:` bug fix
  - `docs:` documentation
  - `test:` adding or updating tests
  - `chore:` maintenance tasks

## Pre-commit Hooks

Install pre-commit hooks to automate checks:

```bash
pip install pre-commit
pre-commit install
```

This runs secret detection, linting, and formatting on every commit.

## Testing

| Layer | Framework | Command |
|-------|-----------|---------|
| Frontend | Vitest + Testing Library | `cd frontend && npm test` |
| Backend | pytest + pytest-asyncio | `cd backend && pytest` |
| Integration | Docker Compose | `./tests/integration/test_stack.sh` |

## Pull Request Checklist

- [ ] Tests pass locally (`npm test` and `pytest`)
- [ ] Linting passes (`eslint .` and `ruff check .`)
- [ ] New features include tests
- [ ] Database changes include an Alembic migration
- [ ] PR description explains the "why" not just the "what"

## Project Layout

See [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md) for the full project structure.

## Questions?

Open an issue on GitHub for bugs, feature requests, or questions.
