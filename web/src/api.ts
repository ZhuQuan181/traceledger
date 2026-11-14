import type {
  Comparison,
  HistoryPage,
  ModelInfo,
  Payload,
  RunRow,
  RunStatus,
} from "./types";

let pickleTokenPromise: Promise<string> | null = null;

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    let msg = text;
    try { msg = JSON.parse(text).detail ?? text; } catch { /* keep text */ }
    throw new Error(msg || `请求失败 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

async function getPickleToken(): Promise<string> {
  if (!pickleTokenPromise) {
    pickleTokenPromise = fetch("/api/session")
      .then((res) => json<{ pickle_token: string }>(res))
      .then((data) => data.pickle_token)
      .catch((err) => {
        pickleTokenPromise = null;
        throw err;
      });
  }
  return pickleTokenPromise;
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch("/api/models");
  return (await json<{ models: ModelInfo[] }>(res)).models;
}

export async function fetchHistory(): Promise<RunRow[]> {
  const res = await fetch("/api/history?limit=8");
  return (await json<{ runs: RunRow[] }>(res)).runs;
}

export type HistoryQuery = {
  limit?: number;
  offset?: number;
  q?: string;
  model?: string;
  status?: RunStatus | "";
};

export async function fetchHistoryPage(query: HistoryQuery = {}): Promise<HistoryPage> {
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 30));
  params.set("offset", String(query.offset ?? 0));
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.model) params.set("model", query.model);
  if (query.status) params.set("status", query.status);
  const res = await fetch(`/api/history?${params.toString()}`);
  return json<HistoryPage>(res);
}

export async function updateRunMeta(
  id: string,
  patch: { note?: string; status?: RunStatus },
): Promise<{ id: string; note: string; status: RunStatus; updated_at: string }> {
  const res = await fetch(`/api/history/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return json(res);
}

export async function deleteRun(id: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/history/${encodeURIComponent(id)}`, { method: "DELETE" });
  return json(res);
}

export async function pruneHistory(
  keep: number,
): Promise<{ deleted: number; remaining: number }> {
  const res = await fetch(`/api/history?keep=${encodeURIComponent(String(keep))}`, {
    method: "DELETE",
  });
  return json(res);
}

export async function fetchComparison(ids: string[]): Promise<Comparison> {
  const res = await fetch(`/api/compare?ids=${encodeURIComponent(ids.join(","))}`);
  return json<Comparison>(res);
}

export async function loadRun(id: string): Promise<Payload> {
  return json<Payload>(await fetch(`/api/history/${id}`));
}

export type RunParams = {
  seed: number;
  split: "temporal" | "random" | "group";
  test_size: number;
  validation_size: number;
  models: string[];
  threshold: number;
  threshold_mode: "fixed" | "f1" | "fpr";
  target_fpr: number;
  ablate?: string | null;
};

export type DemoParams = RunParams & { normal: number; attack: number; leaky?: boolean };

export async function runDemo(p: DemoParams): Promise<Payload> {
  const res = await fetch("/api/demo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...p, explain: true }),
  });
  return json<Payload>(res);
}

export async function runUpload(
  file: File,
  p: RunParams,
  labels?: File | null,
  allowPickle = false
): Promise<Payload> {
  const form = new FormData();
  form.append("file", file);
  if (labels) form.append("labels", labels);
  form.append("split", p.split);
  form.append("test_size", String(p.test_size));
  form.append("validation_size", String(p.validation_size));
  form.append("models", p.models.join(","));
  form.append("threshold", String(p.threshold));
  form.append("threshold_mode", p.threshold_mode);
  form.append("target_fpr", String(p.target_fpr));
  form.append("seed", String(p.seed));
  if (p.ablate) form.append("ablate", p.ablate);
  form.append("allow_pickle", String(allowPickle));
  const headers: Record<string, string> = {};
  if (allowPickle) headers["X-FlowLab-Pickle-Token"] = await getPickleToken();
  const res = await fetch("/api/upload", { method: "POST", body: form, headers });
  return json<Payload>(res);
}
