# Claude Execution Prompt

Use the prompt below when handing the active build back to Claude.

```text
You are working in the canonical Seen-It-First repo:

C:\Users\mark\Documents\Seen-It-First

Treat GitHub as the source of truth. Do not treat Playground or C:\LPR_Training as the main codebase.

Read these first:
- docs/ENGINEERING_EXECUTION_PLAN.md
- docs/BUILD_RULES.md
- docs/GO_LIVE_SOFTWARE_CHECKLIST.md
- docs/OKLAHOMA_PHASE3_WORKFLOW.md

Execution plan:
1. Keep building from the canonical repo only.
2. Push verified checkpoints to GitHub so local and remote state do not drift.
3. Preserve the repossession-focused operator workflow: this UI is for wrecker use while driving, so usability and clarity beat novelty.
4. Keep the design tactical, modern, and durable, but avoid copying the uploaded UI references literally.
5. Avoid shipping mock-only production surfaces. If a screen is still preview-only, either wire it to live repo data or mark it clearly as preview-only.

Current product priorities:
1. Dashboard hardening for real field use
2. Jetson deployment readiness
3. Oklahoma and tribal OCR/detection pipeline readiness

Specific dashboard expectations:
- Large touch targets
- High contrast and glanceable status
- Strong hotlist, camera, and navigation workflow
- Fast operator comprehension while the vehicle is moving
- Sensible degraded states if GPS, cameras, API, or network are unavailable

Known issues to resolve before deployment if they still exist:
- Hotlist view must not rely on static mock alerts
- Camera view must not present hardcoded cameras as live production state
- Field settings must persist to real config or API paths, not local component state only
- Navigation UI must honor backend current position when browser geolocation is unavailable
- Remove mojibake or broken glyph encoding from visible UI strings

Workflow rules:
- Stay on a Claude branch
- Run a checkpoint before push:
  powershell -ExecutionPolicy Bypass -File .\scripts\repo_checkpoint.ps1 -FetchOrigin -RunDashboardBuild -RunPythonChecks
- Push after each verified slice so the repo reflects the actual state of the project

Do not move code back into Playground. Keep new work in this repo.
```
