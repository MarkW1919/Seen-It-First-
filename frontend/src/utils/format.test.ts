import { describe, it, expect } from "vitest";
import { formatVehicleDescription } from "./format";

describe("formatVehicleDescription", () => {
  it("returns full description with all fields", () => {
    expect(
      formatVehicleDescription({
        vehicle_year: 2019,
        vehicle_color: "Blue",
        vehicle_make: "Honda",
        vehicle_model: "Civic",
      })
    ).toBe("2019 Blue Honda Civic");
  });

  it("omits null fields", () => {
    expect(
      formatVehicleDescription({
        vehicle_year: null,
        vehicle_color: "Red",
        vehicle_make: "Ford",
        vehicle_model: null,
      })
    ).toBe("Red Ford");
  });

  it("omits undefined fields", () => {
    expect(
      formatVehicleDescription({
        vehicle_make: "Toyota",
        vehicle_model: "Camry",
      })
    ).toBe("Toyota Camry");
  });

  it("returns empty string when all fields are null", () => {
    expect(
      formatVehicleDescription({
        vehicle_year: null,
        vehicle_color: null,
        vehicle_make: null,
        vehicle_model: null,
      })
    ).toBe("");
  });

  it("returns empty string for empty object", () => {
    expect(formatVehicleDescription({})).toBe("");
  });

  it("handles year-only description", () => {
    expect(
      formatVehicleDescription({ vehicle_year: 2023 })
    ).toBe("2023");
  });

  it("filters out 0 (falsy year)", () => {
    expect(
      formatVehicleDescription({
        vehicle_year: 0,
        vehicle_color: "White",
      })
    ).toBe("White");
  });
});
