import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PlateDisplay from "./PlateDisplay";

describe("PlateDisplay", () => {
  it("renders plate text", () => {
    render(<PlateDisplay plateText="ABC1234" />);
    expect(screen.getByText("ABC1234")).toBeInTheDocument();
  });

  it("shows state code when provided", () => {
    render(<PlateDisplay plateText="ABC1234" state="CA" />);
    expect(screen.getByText("CA")).toBeInTheDocument();
  });

  it("hides state when not provided", () => {
    render(<PlateDisplay plateText="ABC1234" />);
    expect(screen.queryByText("CA")).not.toBeInTheDocument();
  });

  it("displays confidence as percentage", () => {
    render(<PlateDisplay plateText="ABC1234" confidence={0.95} />);
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("hides confidence when not provided", () => {
    const { container } = render(<PlateDisplay plateText="ABC1234" />);
    expect(container.querySelector(".text-success-400")).not.toBeInTheDocument();
  });

  it("applies green color for high confidence (>=0.9)", () => {
    render(<PlateDisplay plateText="ABC1234" confidence={0.92} />);
    const badge = screen.getByText("92%");
    expect(badge.className).toContain("text-success-400");
  });

  it("applies yellow color for medium confidence (0.7-0.9)", () => {
    render(<PlateDisplay plateText="ABC1234" confidence={0.75} />);
    const badge = screen.getByText("75%");
    expect(badge.className).toContain("text-warning-400");
  });

  it("applies red color for low confidence (<0.7)", () => {
    render(<PlateDisplay plateText="ABC1234" confidence={0.55} />);
    const badge = screen.getByText("55%");
    expect(badge.className).toContain("text-danger-400");
  });

  it("applies alert styling when isAlert is true", () => {
    const { container } = render(
      <PlateDisplay plateText="ABC1234" isAlert={true} />
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("border-danger-500");
    expect(wrapper.className).toContain("alert-flash");
  });

  it("applies default styling when isAlert is false", () => {
    const { container } = render(<PlateDisplay plateText="ABC1234" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("bg-slate-700");
    expect(wrapper.className).toContain("border-slate-500");
  });

  it("renders small size variant", () => {
    const { container } = render(
      <PlateDisplay plateText="ABC1234" size="sm" />
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("text-sm");
  });

  it("renders large size variant", () => {
    const { container } = render(
      <PlateDisplay plateText="ABC1234" size="lg" />
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("text-2xl");
  });

  it("defaults to medium size", () => {
    const { container } = render(<PlateDisplay plateText="ABC1234" />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("text-lg");
  });

  it("renders confidence at boundary 0.9 as green", () => {
    render(<PlateDisplay plateText="X" confidence={0.9} />);
    const badge = screen.getByText("90%");
    expect(badge.className).toContain("text-success-400");
  });

  it("renders confidence at boundary 0.7 as yellow", () => {
    render(<PlateDisplay plateText="X" confidence={0.7} />);
    const badge = screen.getByText("70%");
    expect(badge.className).toContain("text-warning-400");
  });
});
