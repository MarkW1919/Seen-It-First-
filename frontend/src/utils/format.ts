/**
 * Build a human-readable vehicle description from optional fields.
 * e.g. "2019 Blue Honda Civic"
 */
export function formatVehicleDescription(vehicle: {
  vehicle_year?: number | null;
  vehicle_color?: string | null;
  vehicle_make?: string | null;
  vehicle_model?: string | null;
}): string {
  return [
    vehicle.vehicle_year,
    vehicle.vehicle_color,
    vehicle.vehicle_make,
    vehicle.vehicle_model,
  ]
    .filter(Boolean)
    .join(" ");
}
