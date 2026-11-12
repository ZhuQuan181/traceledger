export type Warning = {
  rule: string;
  columns: (string | number)[];
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
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
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

export type Payload = {
  dataset: {
    source: string;
    rows: number;
    train: number;
    test: number;
    hash: string;
    split: string;
    threshold: number;
  };
  warnings: Warning[];
  results: Result[];
  best_model: string | null;
  top_flows: TopFlow[];
  report_md: string;
};

export type ModelInfo = { name: string; kind: string };
