# Go-Live Software Checklist (Seen-It-First Edge)

This checklist summarizes the **remaining software/build tasks** to move from repo state to a runnable deployment.

## 1) Environment and dependencies

- [ ] Provision Jetson Orin Nano Super with JetPack 6.x.
- [ ] Create Python venv with system site packages.
- [ ] Install Python dependencies from `requirements.txt`.

Reference commands are documented in `README.md`.

## 2) Required runtime folders and data files

- [ ] Run `python scripts/bootstrap_runtime.py` to create local runtime directories/files.
- [ ] Replace starter hotlist CSV (`data/hotlist.csv`) with your real hotlist feed.
- [ ] Confirm DB path target (`data/seen_it_first.db`) and evidence paths are writable by the runtime user.

## 3) Camera and system configuration

- [ ] Update `edge/camera/config.yaml` with your actual sensor/RTSP sources and enable only installed cameras.
- [ ] Run `python scripts/validate_config.py` and resolve any ERROR results.
- [ ] Verify `edge/config/system.yaml` values for:
  - camera ingest geometry/FPS,
  - thermal thresholds,
  - API host/port,
  - navigation endpoints (`nominatim_url`, `osrm_url`),
  - hotlist/audio behavior.

## 4) Model assets (hard blocker)

- [ ] Download pretrained Phase-1 models (`scripts/download_models.py`).
- [ ] Build TensorRT engines (`scripts/build_tensorrt_engines.py`).
- [ ] Place generated engine files under `models/` matching paths in `edge/config/system.yaml`:
  - `models/vehicle/vehicle.engine`
  - `models/plate/plate.engine`
  - `models/ocr/ocr.engine`
  - `models/classifier/classifier.engine`

If these are missing, startup continues but detection quality/capability is degraded.

## 5) Preflight gate (what can be completed now)

- [ ] Run `python scripts/preflight_check.py` and clear all BLOCKER items.
- [ ] Use `--strict` for a production-grade check (`python scripts/preflight_check.py --strict`).

## 6) Service bring-up and verification

- [ ] Start locally via `python -m edge.main`.
- [ ] Confirm:
  - cameras initialize,
  - API starts on configured host/port,
  - inference loop runs,
  - detections/alerts are written to SQLite.
- [ ] Run `scripts/test_pipeline.py` for pipeline-level smoke validation.

## 7) Productionization

- [ ] Install to `/opt/seen-it-first` with correct ownership.
- [ ] Install and enable the provided systemd unit: `systemd/seen-it-first-edge.service`.
- [ ] Validate reboot persistence and log monitoring (`journalctl -u seen-it-first-edge -f`).

## 8) Post-MVP software tasks (non-blocking for initial run)

- [ ] Replace public Nominatim/OSRM endpoints with self-hosted services for reliability.
- [x] Added baseline config validation tests (`python -m unittest tests.test_validate_config`).
- [ ] Plan Phase-3 custom training only if baseline pretrained performance is insufficient.
