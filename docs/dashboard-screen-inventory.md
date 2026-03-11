# Dashboard Screen Inventory

The dashboard now supports two preview paths:

1. **Navigation workflow preview** (`NavigationPage`) using `?preview=base|route|arrived`
2. **Operations console preview** (`OpsPreviewPage`) using `?screen=hotlist|cameras|settings`

## Navigation preview states
Use URL query `preview`:

- `?preview=base` → Destination selected, not navigating.
- `?preview=route` → Active navigation with route card + route polyline.
- `?preview=arrived` → ARRIVED banner + scanning panel + ranked vehicle cards.

## Operations preview screens
Use URL query `screen`:

- `?screen=hotlist` → Active hotlist alert cards (plate, reason, priority, camera, timestamp).
- `?screen=cameras` → Multi-camera grid with feed placeholders + status/FPS/temp metadata, plus recent alerts directly below camera windows.
- `?screen=settings` → System settings panel.


- Recent alerts table now includes **GPS coordinates** and deep links into navigation preview.
- Clicking coordinates (or View Directions) opens `/?preview=route&alert=<id>` to preload destination, route directions, and a selected LPR detail card with scan photo.

- On `?screen=cameras`, clicking any recent-alert row now selects it and opens a detailed alert/vehicle panel with scan photo.
- Added quick-action controls for recovery workflow (e.g., **License Plate Search**, **Settings**, and **Manual PTZ Control**).
- Manual PTZ Control opens a luxury-style PTZ modal with cinematic styling, preset chips, joystick pad, telemetry panel, and zoom/focus/speed controls.

- In Navigation, geocoding an address now auto-searches stored detections near that address and shows either a subtle "no detections" notice or a selection modal with detection details/images.

## Source of truth
- `dashboard/src/App.tsx`
- `dashboard/src/pages/NavigationPage.tsx`
- `dashboard/src/pages/OpsPreviewPage.tsx`
- `dashboard/src/components/TargetList.tsx`
- `dashboard/src/components/VehicleDetectionCard.tsx`
- `dashboard/src/hooks/useWebSocket.ts`
