export const num = (v: number | null | undefined, digits = 4) =>
  v == null ? "—" : v.toFixed(digits);

export const pct = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;

export const secs = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(2)}s`);

export const int = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("en-US");
