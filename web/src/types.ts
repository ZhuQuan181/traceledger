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
  threshold_source?: "fixed" | "validation_f1" | "validation_fpr";
  threshold_target_fpr?: number | null;
  threshold_scan: {
    threshold: number;
    precision: number;
    recall: number;
    f1: number;
    fpr: number | null;
  }[];
  roc_curve: { fpr: number; tpr: number; threshold: number | null }[];
  pr_curve: { precision: number; recall: number; threshold: number | null }[];
  calibration: { mean_predicted: number; fraction_positive: number }[];
  brier_score: number | null;
  calibration_note: string;
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
  threshold_mode?: "fixed" | "f1" | "fpr";
  threshold_source?: "fixed" | "validation_f1" | "validation_fpr";
  threshold_target_fpr?: number | null;
  seed?: number;
  attack_train?: number;
  attack_validation?: number;
  attack_test?: number;
  selection?: { rule: string; validation_auc: number | null; test_auc: number | null };
  labels?: { mode?: string; labelled?: number; total?: number; file?: string };
  engineering?: { min_duration_ms?: number; derived?: string[]; note?: string };
  format?: { format?: string; shape?: string; note?: string; pickle_object?: string };
  classes?: { label: string; count: number }[];
  quality?: {
    rows: number;
    class_count: number;
    missing_labels: number;
    duplicate_rows: number;
    duplicate_rate: number;
    rare_threshold: number;
    rare_classes: { label: string; count: number }[];
    rare_test_labels: { label: string; total: number }[];
    conflict_key: string | null;
    conflict_groups: number;
    conflict_rows: number;
    conflict_examples: { entity: string; labels: string[]; rows: number }[];
  };
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
  environment?: {
    flowlab?: string;
    python?: string;
    pandas?: string | null;
    numpy?: string | null;
    scikit_learn?: string | null;
  };
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
  threshold_mode: "fixed" | "f1" | "fpr";
  target_fpr: number;
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

export type RunStatus = "unreviewed" | "baseline" | "failed" | "archived";

export type RunRow = {
  id: string;
  schema_version?: number;
  created_at: string;
  updated_at?: string | null;
  source: string;
  dataset_hash: string;
  split: string;
  rows: number;
  validation?: number;
  test?: number;
  threshold?: number;
  best_model: string | null;
  best_auc: number | null;
  best_validation_auc?: number | null;
  models?: string[];
  fingerprint?: string | null;
  note?: string;
  status?: RunStatus;
};

export type HistoryPage = {
  runs: RunRow[];
  total: number;
  available: number;
  db_bytes: number;
  wal_bytes?: number;
  payload_bytes?: number;
  payload_raw_bytes?: number;
  models: string[];
};

export type ComparisonCheck = {
  key: "dataset" | "features" | "split";
  label: string;
  ok: boolean;
  detail: string;
};

export type ComparisonDelta = {
  validation_auc: number | null;
  test_auc: number | null;
  pr_auc: number | null;
  f1: number | null;
  recall: number | null;
  fpr: number | null;
};

export type ComparisonRun = {
  id: string;
  created_at: string;
  source: string;
  dataset_hash: string;
  split: string;
  seed?: number | null;
  rows?: number | null;
  train?: number | null;
  validation?: number | null;
  validation_size?: number | null;
  test?: number | null;
  attack_test?: number | null;
  model: string | null;
  validation_auc: number | null;
  test_auc: number | null;
  pr_auc: number | null;
  f1: number | null;
  precision: number | null;
  recall: number | null;
  fpr: number | null;
  threshold: number | null;
  threshold_source?: "fixed" | "validation_f1" | "validation_fpr" | null;
  threshold_mode?: "fixed" | "f1" | "fpr" | null;
  duration_s: number | null;
  features: string[];
  encoded_features?: number | null;
  experiment_fingerprint?: string | null;
  delta: ComparisonDelta;
};

export type Comparison = {
  status: "comparable" | "limited" | "incompatible";
  comparable: boolean;
  headline: string;
  warnings: string[];
  checks: ComparisonCheck[];
  baseline_run_id: string;
  command: string;
  runs: ComparisonRun[];
  markdown: string;
};

export type ModelInfo = { name: string; kind: string };

export type JobStatus =
  | "queued"
  | "running"
  | "cancelling"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "interrupted";

export type Job = {
  job_id: string;
  kind: "demo" | "upload" | "score" | "test";
  status: JobStatus;
  phase: "queued" | "loading" | "validating" | "features" | "model" | "ablation" | "report" | "done";
  completed_models: number;
  total_models: number;
  percent: number;
  message: string;
  elapsed_s: number;
  run_id: string | null;
  error: string | null;
  has_ablation: boolean;
  result_available: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ScoreRow = {
  score: number;
  src_ip?: string | null;
  dst_ip?: string | null;
  src_port?: number | null;
  dst_port?: number | null;
  protocol?: number | string | null;
  timestamp?: string | null;
  duration_ms?: number | null;
  fwd_packets?: number | null;
  bwd_packets?: number | null;
  fwd_bytes?: number | null;
  bwd_bytes?: number | null;
  bytes_per_s?: number | null;
  packets_per_s?: number | null;
};

export type ScorePayload = {
  mode: "score";
  generated_at: string;
  source: string;
  dataset: {
    source: string;
    rows: number;
    columns: number;
    hash: string;
    format?: Record<string, unknown>;
    labels?: Record<string, unknown> | null;
  };
  model: { name: string; kind: "unsupervised" };
  top: ScoreRow[];
  summary: {
    returned: number;
    scored_rows: number;
    max_score: number | null;
    median_top_score: number | null;
    p95_top_score: number | null;
  };
  warnings?: { rule: string; severity: string; message: string }[];
  note: string;
};

export type PreflightStatus = "pass" | "warn" | "fail";

export type PreflightCheck = {
  key: string;
  label: string;
  status: PreflightStatus;
  scope: "evaluation" | "scoring" | "both";
  detail: string;
  hint: string | null;
};

export type ColumnMapping = {
  original: string;
  normalized: string;
  canonical: string;
  mapped: boolean;
  role: string | null;
};

export type SplitCoverage = {
  split: "train" | "validation" | "test";
  rows: number;
  benign: number;
  attack: number;
};

export type PreflightResult = {
  source: string;
  dataset: {
    rows: number;
    columns: number;
    features: number;
    hash: string;
  };
  column_mapping: ColumnMapping[];
  checks: PreflightCheck[];
  missing: {
    cells: number;
    columns: { column: string; missing: number }[];
  };
  non_finite: {
    cells: number;
    columns: Record<string, number>;
  };
  timestamp: {
    column: string | null;
    parse_rate: number | null;
    invalid: number | null;
  };
  labels: {
    present: boolean;
    missing?: number;
    classes: { label: string; count: number; kind: "benign" | "attack" }[];
    benign?: number;
    attack?: number;
  };
  split: {
    requested: "temporal" | "random" | "group";
    effective: "temporal" | "random" | "group";
    fell_back: boolean;
    coverage: SplitCoverage[];
    entity_key: string | null;
    warnings: string[];
  } | null;
  ready_for_evaluation: boolean;
  ready_for_scoring: boolean;
  blockers: {
    evaluation: string[];
    scoring: string[];
  };
};
