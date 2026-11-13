export type Warning = {
  rule: string;
  columns: (string | number)[];
  value?: number;
  severity: "high" | "medium" | "low";
  message: string;
  suggestion: string;
};

export type Metrics = {
  auc: number | null;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  fpr: number | null;
  support: number;
  attack_support: number;
};

export type TopFlow = {
  src_ip?: string;
  dst_ip?: string;
  dst_port?: number;
  protocol?: number;
  timestamp?: string;
  fwd_packets?: number;
  label?: string;
  score: number;
};

export type Result = {
  model: string;
  kind: "supervised" | "unsupervised";
  metrics: Metrics;
  confusion: { tn: number; fp: number; fn: number; tp: number };
  duration_s: number;
  params: Record<string, unknown>;
  split: string;
  dataset_hash: string;
  n_train: number;
  n_test: number;
  threshold: number;
  seed?: number;
  attack_train?: number;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
};

export type Dataset = {
  source: string;
  rows: number;
  train: number;
  test: number;
  hash: string;
  split: string;
  threshold: number;
  seed?: number;
  attack_train?: number;
  attack_test?: number;
  labels?: { mode?: string; labelled?: number; total?: number; file?: string };
  engineering?: { min_duration_ms?: number; derived?: string[]; note?: string };
  format?: { format?: string; shape?: string; note?: string; pickle_object?: string };
};

export type Ablation = {
  column: string;
  rows: { model: string; auc_with: number | null; auc_without: number | null; delta: number | null }[];
  note: string;
};

export type Payload = {
  dataset: Dataset;
  warnings: Warning[];
  results: Result[];
  best_model: string | null;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
  ablation?: Ablation | null;
  report_md: string;
  report_html: string;
  run_id?: string;
};

export type RunRow = {
  id: string;
  created_at: string;
  source: string;
  dataset_hash: string;
  split: string;
  rows: number;
  best_model: string | null;
  best_auc: number | null;
};

export type ModelInfo = { name: string; kind: string };
