# Engineering Execution Plan

This document is the working agreement for ongoing Seen-It-First development.

## Source Of Truth

- Canonical repo: `C:\Users\mark\Documents\Seen-It-First`
- GitHub is the source of truth for project state.
- `C:\LPR_Training` is runtime/training output and staging only, not the authoritative codebase.
- `C:\Users\mark\Documents\Playground` is no longer a build source of truth for this project.

## Mission

Finish and deploy a repossession-focused LPR and vehicle intelligence system for:

- NVIDIA Jetson Orin Nano in the wrecker
- Windows 11 laptop operator console
- US-only license plates with Oklahoma and tribal priority

The system must be practical while driving, visually readable in poor conditions, and robust under degraded connectivity.

## Current Status

Completed or actively in place:

- Jetson runtime/install and preflight improvements
- Optional vehicle classifier runtime bridge
- Oklahoma and tribal OCR synthetic data groundwork
- Dashboard redesign work in progress
- Canonical repo established and separate from ad hoc workspaces

Still not complete:

- Production-ready dashboard data wiring
- Final Jetson deployment configuration
- Real Oklahoma tribal plate detection dataset
- Full deployment verification on target hardware

## Immediate Execution Order

1. Dashboard hardening
   - Keep the operator-first command-center design.
   - Remove or clearly isolate mock data from production surfaces.
   - Prioritize large targets, glanceable status, and low cognitive load for driving use.
   - Preserve a high-end technical look without sacrificing clarity.

2. Runtime contract cleanup
   - Keep optional vehicle sidecars optional.
   - Ensure startup behavior degrades cleanly when sidecars are absent.
   - Keep config validation and preflight aligned with real deployment expectations.

3. Jetson deployment preparation
   - Finalize camera and LAN example configs.
   - Keep installer, runtime preparation, and preflight as the canonical deployment path.
   - Validate deployment steps in the repo before field use.

4. Oklahoma and tribal training pipeline
   - Keep OCR groundwork in the repo.
   - Add real-world Oklahoma and tribal captures when available.
   - Treat synthetic assets as OCR support, not a replacement for scene data.

## Agent Workflow

### Branching

- Claude work should stay on a Claude branch.
- Codex work should stay on a Codex branch.
- Do not have both agents making unrelated changes on the same branch at the same time.

### Checkpoints

At the end of each coherent slice:

1. Build the affected surface.
2. Run the relevant validation checks.
3. Review the diff for accidental files.
4. Commit with a real message.
5. Push the branch.

### Shared Rules

- Do not keep new project logic outside this repo.
- Do not commit generated runtime artifacts, logs, or datasets unless intentionally tracked.
- If a UI surface is still preview-only, label it as preview-only or wire it to live data before deployment.
- Do not treat successful visual rendering as deployment readiness.

## Definition Of Done Per Slice

A slice is ready to hand off only when:

1. The changed code builds cleanly.
2. The relevant tests or checks pass.
3. The runtime assumptions are documented if they changed.
4. The branch is pushed so GitHub reflects the new state.

## Recommended Local Checkpoint Command

Use the helper script from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\repo_checkpoint.ps1 -FetchOrigin -RunDashboardBuild -RunPythonChecks
```

This is the standard pre-push checkpoint for local work.
