import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Result } from "../types";
import { InvestigationPanel } from "./InvestigationPanel";

const result = {
  by_label: [
    { label: "DDoS", kind: "attack", total: 20, flagged: 15, rate: 0.75 },
    { label: "BENIGN", kind: "benign", total: 80, flagged: 4, rate: 0.05 },
  ],
  source_ranking: [
    { src_ip: "10.0.0.9", alerts: 12, true_attacks: 10, false_alarms: 2, max_score: 0.99 },
  ],
  false_negatives: [
    { src_ip: "10.0.0.5", dst_ip: "10.0.0.7", dst_port: 80, score: 0.44, label: "DDoS" },
  ],
  false_positives: [],
} as Result;

describe("InvestigationPanel", () => {
  it("shows class recall, false alarm rate, and the first source to inspect", () => {
    render(<InvestigationPanel result={result} />);
    expect(screen.getAllByText("DDoS").length).toBeGreaterThan(0);
    expect(screen.getByText("75.00%")).toBeInTheDocument();
    expect(screen.getByText("5.00%")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.9")).toBeInTheDocument();
    expect(screen.getByText(/典型漏报/)).toBeInTheDocument();
  });
});
