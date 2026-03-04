# Contributing to SEEN IT FIRST

## Branch Strategy

| Branch         | Purpose                                  |
|----------------|------------------------------------------|
| `main`         | Production-ready releases                |
| `develop`      | Integration branch for active work       |
| `feature/*`    | New features (branch from develop)       |
| `hotfix/*`     | Critical production fixes (branch from main) |
| `model/*`      | AI model training, tuning, conversion    |
| `dashboard/*`  | Dashboard UI changes                     |

## Feature Branch Workflow

1. Create branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. Make changes, commit with conventional messages.

3. Push and open a pull request into `develop`:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. After review, merge into `develop`. When `develop` is stable, merge into `main`.

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add plate OCR confidence boosting
fix: resolve camera reconnect deadlock on Housing B
docs: update inference scheduling table
refactor: extract thermal monitor to utils
test: add fusion engine hotlist matching tests
chore: update TensorRT dependency to 10.x
```

**Scope prefixes** (when useful):

```
feat(camera): add IMX462 CSI pipeline auto-detection
fix(api): correct WebSocket heartbeat interval
feat(dashboard): add PTZ preset quick-select buttons
```

## Code Style

**Python (edge/):**
- Python 3.10+
- Format with `ruff format`
- Lint with `ruff check`
- Type hints on public functions
- Docstrings on modules and classes

**TypeScript (dashboard/):**
- Strict mode enabled
- Format with Prettier
- Lint with ESLint
- Functional React components with hooks

## Testing

- Python tests: `pytest tests/`
- Dashboard tests: `cd dashboard && npm test`
- Verify Python syntax: `python3 -m py_compile edge/main.py`

## Pull Request Checklist

- [ ] Code follows the style guidelines
- [ ] Self-review completed
- [ ] Tests added for new functionality
- [ ] All existing tests pass
- [ ] Documentation updated if needed
- [ ] No hardcoded IPs, paths, or secrets
- [ ] Configuration changes use YAML config files
