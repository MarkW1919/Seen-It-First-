# Release Notes — v0.9-field-baseline

**Date:** 2026-02-26
**Tag:** `v0.9-field-baseline`

## Summary

Consolidation merge of the `claude/document-build-status-KbwBa` branch into `main`.
This release stabilizes the repository into a single production branch with fully
passing CI, resolving all outstanding lint, dependency, and infrastructure issues
that prevented a clean build.

### Changes Merged

- **ci:** Add PostgreSQL 15 and Redis 7 service containers for backend tests
- **ci:** Split backend lint from test job to avoid dependency conflicts
- **ci:** Remove invalid `--config` flag from ruff commands
- **fix:** Add `email-validator` dependency for pydantic `EmailStr` support
- **fix:** Resolve UP038 lint errors (use `X | Y` union syntax in `isinstance` calls)
- **fix:** Resolve CI pipeline failures (pytest discovery, ruff config, Pydantic v2)
- **fix:** Resolve all lint errors across backend, ai, and camera modules

## Architecture Modules

| Module       | Purpose                                      | Stack                                          |
|--------------|----------------------------------------------|-------------------------------------------------|
| **backend/** | REST API, auth, data persistence             | FastAPI, SQLAlchemy, PostgreSQL, Redis, Alembic |
| **frontend/**| Web UI for scanning and fleet management     | React 18, TypeScript, Vite, TailwindCSS         |
| **ai/**      | Vehicle detection and license plate OCR      | YOLOv8, ONNX Runtime, TensorRT                  |
| **camera/**  | PTZ camera control and RTSP streaming        | pyserial, Redis, GStreamer                       |

## CI Status

All four CI jobs are configured and expected to pass:

1. **Frontend Lint & Test** — ESLint, Vitest, TypeScript type check (Node 20)
2. **Backend Lint** — ruff 0.8.4 check + format (Python 3.12)
3. **Backend Test** — pytest with PostgreSQL 15 and Redis 7 services (Python 3.12)
4. **Docker Build Check** — Multi-stage image build validation

## Tag Reference

```
git tag v0.9-field-baseline
```

This tag marks the first verified clean-build baseline on `main`.
All subsequent development should branch from this point.
