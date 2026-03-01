import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DetectionCard from "./DetectionCard";
import type { Detection } from "../types";

function makeDetection(overrides: Partial<Detection> = {}): Detection {
  return {
    id: "det-1",
    agent_id: null,
    session_id: null,
    vehicle_type: "sedan",
    vehicle_color: "Blue",
    vehicle_make: "Honda",
    vehicle_model: "Civic",
    vehicle_year: 2019,
    vehicle_confidence: 0.88,
    image_path: null,
    thumbnail_path: null,
    latitude: 34.0522,
    longitude: -118.2437,
    address: "123 Main St, Los Angeles, CA",
    heading: 270,
    speed: 35,
    extra: {},
    created_at: "2026-02-20T14:30:00Z",
    plate_reads: [
      {
        id: "pr-1",
        plate_text: "ABC1234",
        plate_state: "CA",
        plate_type: null,
        confidence: 0.95,
        plate_image_path: null,
        raw_ocr: null,
        created_at: "2026-02-20T14:30:00Z",
      },
    ],
    ...overrides,
  };
}

describe("DetectionCard", () => {
  describe("full (non-compact) mode", () => {
    it("renders plate text from first plate read", () => {
      render(<DetectionCard detection={makeDetection()} />);
      expect(screen.getByText("ABC1234")).toBeInTheDocument();
    });

    it("renders vehicle description", () => {
      render(<DetectionCard detection={makeDetection()} />);
      expect(screen.getByText("2019 Blue Honda Civic")).toBeInTheDocument();
    });

    it("renders address when present", () => {
      render(<DetectionCard detection={makeDetection()} />);
      expect(
        screen.getByText("123 Main St, Los Angeles, CA")
      ).toBeInTheDocument();
    });

    it("hides address when not present", () => {
      render(
        <DetectionCard detection={makeDetection({ address: null })} />
      );
      expect(
        screen.queryByText("123 Main St, Los Angeles, CA")
      ).not.toBeInTheDocument();
    });

    it("renders speed and heading", () => {
      render(<DetectionCard detection={makeDetection()} />);
      expect(screen.getByText(/35 mph/)).toBeInTheDocument();
      expect(screen.getByText(/heading 270/)).toBeInTheDocument();
    });

    it("hides speed when null", () => {
      render(
        <DetectionCard detection={makeDetection({ speed: null })} />
      );
      expect(screen.queryByText(/mph/)).not.toBeInTheDocument();
    });

    it("renders additional plate reads", () => {
      const detection = makeDetection({
        plate_reads: [
          {
            id: "pr-1",
            plate_text: "ABC1234",
            plate_state: "CA",
            plate_type: null,
            confidence: 0.95,
            plate_image_path: null,
            raw_ocr: null,
            created_at: "2026-02-20T14:30:00Z",
          },
          {
            id: "pr-2",
            plate_text: "XYZ9876",
            plate_state: "NV",
            plate_type: null,
            confidence: 0.88,
            plate_image_path: null,
            raw_ocr: null,
            created_at: "2026-02-20T14:30:01Z",
          },
        ],
      });
      render(<DetectionCard detection={detection} />);
      expect(screen.getByText("ABC1234")).toBeInTheDocument();
      expect(screen.getByText("XYZ9876")).toBeInTheDocument();
    });

    it("applies alert styling when isAlert is true", () => {
      const { container } = render(
        <DetectionCard detection={makeDetection()} isAlert={true} />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain("border-danger-500");
    });
  });

  describe("compact mode", () => {
    it("renders as a button element", () => {
      render(
        <DetectionCard detection={makeDetection()} compact={true} />
      );
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("renders plate text", () => {
      render(
        <DetectionCard detection={makeDetection()} compact={true} />
      );
      expect(screen.getByText("ABC1234")).toBeInTheDocument();
    });

    it("fires onClick when clicked", () => {
      const onClick = vi.fn();
      render(
        <DetectionCard
          detection={makeDetection()}
          compact={true}
          onClick={onClick}
        />
      );
      fireEvent.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledOnce();
    });

    it("shows location icon when latitude is present", () => {
      const { container } = render(
        <DetectionCard detection={makeDetection()} compact={true} />
      );
      expect(container.querySelector("svg")).toBeInTheDocument();
    });

    it("hides location icon when latitude is null", () => {
      // No SVG for location when latitude is null.
      // The component only renders the SVG if detection.latitude is truthy.
      const { container } = render(
        <DetectionCard
          detection={makeDetection({ latitude: null })}
          compact={true}
        />
      );
      expect(container.querySelector("svg")).not.toBeInTheDocument();
    });
  });

  it("handles empty plate reads gracefully", () => {
    const detection = makeDetection({ plate_reads: [] });
    const { container } = render(<DetectionCard detection={detection} />);
    // Should render without crashing, plate section is conditional
    expect(container.firstChild).toBeInTheDocument();
  });

  it("renders partial vehicle description", () => {
    const detection = makeDetection({
      vehicle_year: null,
      vehicle_color: "Red",
      vehicle_make: "Ford",
      vehicle_model: null,
    });
    render(<DetectionCard detection={detection} />);
    expect(screen.getByText("Red Ford")).toBeInTheDocument();
  });
});
