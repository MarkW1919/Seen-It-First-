# Codebase Issue Triage: Status + Next Tasks

## Recently completed

1. **Typo consistency**
   - Updated camera comment wording to use `license-plate` consistently.

2. **Geocoder rate-limit bug**
   - Fixed mixed clock usage by keeping rate-limit timing on `time.monotonic()`.
   - Added regression tests for cache-hit behavior and monotonic delay bounds.

3. **README model path clarification**
   - Clarified distinction between generated runtime artifacts (`models/`) and tracked docs (`edge/models/`).

4. **API hardening baseline**
   - Added optional token auth (`api.auth_token`) for `/navigation/*` and `/ws`.
   - Added configurable CORS origin allowlist (`api.allowed_origins`).
   - Defaulted API bind host to `127.0.0.1` for safer single-user setup.

---

## Next recommended tasks

### 1) Add endpoint-level auth integration tests (HTTP + WebSocket)
**Why:** Current tests should validate middleware/route behavior end-to-end, including websocket rejection/acceptance paths.

### 2) Add startup preflight for deployment readiness
**Why:** Operators need a single check that verifies camera config, model files, DB path writability, and API security settings before runtime.

### 3) Optional: strengthen API auth ergonomics
**Why:** Shared token is suitable for small deployments, but production-like environments may benefit from rotating tokens and stricter origin validation.

### 4) Optional: self-hosted navigation services guidance
**Why:** `nominatim` and `router.project-osrm.org` are public endpoints; documented self-hosting steps improve reliability and policy compliance for sustained use.
