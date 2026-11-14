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
  validation_metrics: Metrics;
  confusion: { tn: number; fp: number; fn: number; tp: number };
  validation_confusion: { tn: number; fp: number; fn: number; tp: number };
  duration_s: number;
  params: Record<string, unknown>;
  split: string;
  split_requested?: string;
  dataset_hash: string;
  n_train: number;
  n_validation: number;
  n_test: number;
  threshold: number;
  threshold_source?: "fixed" | "validation_f1";
  threshold_scan: {
    threshold: number;
    precision: number;
    recall: number;
    f1: number;
    fpr: number | null;
  }[];
  seed?: number;
  attack_train?: number;
  attack_validation?: number;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
  score_curve_basis: "time" | "order";
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
  validation: number;
  test: number;
  hash: string;
  split: string;
  split_requested?: string;
  split_fallback?: boolean;
  generalization?: string;
  split_diagnostics?: {
    duplicate_rows?: number;
    duplicate_cross?: Record<string, number>;
    entity_key?: string | null;
    entity_overlap?: Record<string, number>;
  };
  threshold: number;
  threshold_mode?: "fixed" | "f1";
  threshold_source?: "fixed" | "validation_f1";
  seed?: number;
  attack_train?: number;
  attack_validation?: number;
  attack_test?: number;
  selection?: { rule: string; validation_auc: number | null; test_auc: number | null };
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
  best_model_selection?: string;
  top_flows: TopFlow[];
  score_curve: { p: number; h: number }[];
  score_curve_basis?: "time" | "order";
  threshold_scan?: Result["threshold_scan"];
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
  split: "temporal" | "random" | "group";
  split_effective: string;
  test_size: number;
  validation_size: number;
  seed: number;
  threshold: number;
  threshold_mode: "fixed" | "f1";
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
  schema_version?: number;
  created_at: string;
  source: string;
  dataset_hash: string;
  split: string;
  rows: number;
  validation?: number;
  best_model: string | null;
  best_auc: number | null;
  best_validation_auc?: number | null;
  models?: string[];
  fingerprint?: string | null;
};

export type ModelInfo = { name: string; kind: string };
