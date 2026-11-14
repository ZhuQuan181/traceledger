import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TopFlows } from "./TopFlows";

describe("TopFlows", () => {
  it("describes whether a flow actually crossed the threshold", () => {
    render(
      <TopFlows
        threshold={0.5}
        flows={[
          { src_ip: "10.0.0.1", dst_ip: "10.0.0.2", dst_port: 443, score: 0.9, label: "DDoS" },
          { src_ip: "10.0.0.3", dst_ip: "10.0.0.4", dst_port: 80, score: 0.2, label: "BENIGN" },
        ]}
      />,
    );
    expect(screen.getAllByText("分数超阈值").length).toBeGreaterThan(0);
    expect(screen.getAllByText("高分排序（未过阈值）").length).toBeGreaterThan(0);
  });

  it("marks the leaked port instead of claiming a threshold hit", () => {
    render(
      <TopFlows
        threshold={0.9}
        leakPort={3389}
        flows={[{ src_ip: "a", dst_ip: "b", dst_port: 3389, score: 0.4 }]}
      />,
    );
    expect(screen.getAllByText("端口命中").length).toBeGreaterThan(0);
  });
});
