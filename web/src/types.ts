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
  pr_auc: number | null;
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
  split_requested?: string;
  dataset_hash: string;
  n_train: number;
  n_test: number;
  threshold: number;
  seed?: number;
  attack_train?: number;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
  by_label: InvestigationLabel[];
  false_positives: ErrorExample[];
  false_negatives: ErrorExample[];
  source_ranking: SourceRanking[];
};

export type InvestigationLabel = {
  label: string;
  kind: "benign" | "attack";
  total: number;
  flagged: number;
  rate: number | null;
};

export type ErrorExample = {
  src_ip?: string;
  dst_ip?: string;
  dst_port?: number;
  timestamp?: string;
  score: number;
  label?: string;
};

export type SourceRanking = {
  src_ip: string;
  alerts: number;
  true_attacks: number;
  false_alarms: number;
  max_score: number;
};

export type Dataset = {
  source: string;
  rows: number;
  train: number;
  test: number;
  hash: string;
  split: string;
  split_requested?: string;
  split_fallback?: boolean;
  threshold: number;
  seed?: number;
  attack_train?: number;
  attack_test?: number;
  labels?: { mode?: string; labelled?: number; total?: number; file?: string };
  engineering?: { min_duration_ms?: number; derived?: string[]; note?: string };
  format?: { format?: string; shape?: string; note?: string; pickle_object?: string };
  classes?: { label: string; count: number }[];
  features?: { used: string[]; encoded: number };
  experiment_fingerprint?: string;
};

export type Ablation = {
  column: string;
  rows: { model: string; auc_with: number | null; auc_without: number | null; delta: number | null }[];
  note: string;
};

export type VerdictCheck = { name: string; status: "pass" | "warn" | "fail"; detail: string };

export type Verdict = {
  level: "ok" | "warn" | "fail";
  headline: string;
  reasons: string[];
  checks: VerdictCheck[];
};

export type ChecklistItem = { item: string; ok: boolean; detail: string };

export type Payload = {
  dataset: Dataset;
  experiment: Experiment;
  generated_at: string;
  experiment_fingerprint: string;
  verdict?: Verdict;
  checklist?: ChecklistItem[];
  warnings: Warning[];
  results: Result[];
  best_model: string | null;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
  investigation: {
    by_label: InvestigationLabel[];
    false_positives: ErrorExample[];
    false_negatives: ErrorExample[];
    source_ranking: SourceRanking[];
  };
  ablation?: Ablation | null;
  report_md: string;
  report_html: string;
  run_id?: string;
};

export type Experiment = {
  models: string[];
  split: "temporal" | "random";
  split_effective: string;
  test_size: number;
  seed: number;
  threshold: number;
  explain: boolean;
  ablate: string | null;
  source_kind: "demo" | "upload" | "file";
  source_ref?: string | null;
  normal: number;
  attack: number;
  leaky: boolean;
  source: string;
  command: string;
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
