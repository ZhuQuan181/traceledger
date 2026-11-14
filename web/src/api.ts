import type { ModelInfo, Payload, RunRow } from "./types";

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

export async function loadRun(id: string): Promise<Payload> {
  return json<Payload>(await fetch(`/api/history/${id}`));
}

export type RunParams = {
  seed: number;
  split: "temporal" | "random";
  models: string[];
  threshold: number;
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
  form.append("models", p.models.join(","));
  form.append("threshold", String(p.threshold));
  form.append("seed", String(p.seed));
  if (p.ablate) form.append("ablate", p.ablate);
  form.append("allow_pickle", String(allowPickle));
  const headers: Record<string, string> = {};
  if (allowPickle) headers["X-FlowLab-Pickle-Token"] = await getPickleToken();
  const res = await fetch("/api/upload", { method: "POST", body: form, headers });
  return json<Payload>(res);
}
