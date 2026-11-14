import { describe, expect, it } from "vitest";
import { int, num, pct, secs } from "./format";

describe("format", () => {
  it("keeps unavailable metrics explicit", () => {
    expect(num(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
    expect(secs(null)).toBe("—");
  });

  it("formats metrics without hiding precision", () => {
    expect(num(0.98765)).toBe("0.9877");
    expect(pct(0.0125)).toBe("1.25%");
    expect(secs(1.234)).toBe("1.23s");
    expect(int(1200)).toBe("1,200");
  });
});
