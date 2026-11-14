# FlowLab · Network Traffic Anomaly Detection Workbench

[![CI](https://github.com/ZhuQuan181/traceledger/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ZhuQuan181/traceledger/actions/workflows/ci.yml)
[![Pages](https://github.com/ZhuQuan181/traceledger/actions/workflows/pages.yml/badge.svg?branch=master)](https://zhuquan181.github.io/traceledger/en/)
[![Release](https://img.shields.io/github/v/release/ZhuQuan181/traceledger?display_name=tag&color=0d5d61)](https://github.com/ZhuQuan181/traceledger/releases/latest)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-0d5d61?logo=python&logoColor=white)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-0d5d61?logo=react&logoColor=white)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-0d5d61?logo=docker&logoColor=white)](compose.yaml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-0d5d61)](LICENSE)

**Language:** [中文](README.md) | **English**

> **Turn network traffic anomaly detection research models into systems that run, reproduce, and explain.**

- Created: 2026-11-11
- Current version: **v0.8.0** (2026-11-15: cross-experiment comparison, label-quality diagnostics, searchable history and retention controls, ROC/PR/calibration curves, environment manifests)
- Tests: **168 backend tests + 26 frontend tests**; pcap tests require `tshark`
- Documentation: Chinese and English READMEs, with design docs in Chinese; code and interfaces are in English
- Project site: https://zhuquan181.github.io/traceledger/en/
- Sample report (synthetic data): https://zhuquan181.github.io/traceledger/demo-report.html

[![FlowLab workspace](screens/v11-workspace.png)](https://zhuquan181.github.io/traceledger/en/)

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/); Node.js 22.12+ when changing the frontend;
`tshark` for pcap ingestion.

```bash
git clone https://github.com/ZhuQuan181/traceledger.git
cd traceledger
uv sync --extra dev --extra api --extra data

uv run flowlab sample --rows 2000          # Generate a sample CSV
uv run flowlab demo                        # Run the full pipeline on synthetic data
uv run flowlab demo --report out/report.md --html out/report.html
uv run flowlab run my.csv --split temporal # Run your own CSV (requires a label column)
uv run flowlab run my.csv --split group     # Hold out whole entities for new-host generalization
uv run flowlab run my.csv --threshold-mode f1  # Choose the threshold on validation only
uv run flowlab run cap.pcap                # Auto-align cap.pcap.labels.csv
uv run flowlab run cap.pcap --labels l.csv # Or pass a label file explicitly
uv run flowlab run feats.npz               # npy / npz / parquet / json / jsonl / pkl / xlsx
uv run flowlab run model_input.pkl --allow-pickle   # pickle requires explicit consent
uv run flowlab score cap.pcap --top 20     # Score unlabeled flows without ground truth
uv run flowlab serve                       # Web workbench at 127.0.0.1:8765

uv run python scripts/check_dataset.py data.csv        # Pre-training data check
uv run python scripts/bench_scale.py --rows 690000     # Scale benchmark
cd web && npm ci && npm run build          # Rebuild the frontend
```

`pcap` ingestion requires `tshark` (Ubuntu: `sudo apt install tshark`).
Zeek `conn.log` files can be read directly (`.log` / `.log.gz`); pass sidecar labels with `--labels`.

### Docker

```bash
docker compose up --build                 # http://127.0.0.1:8765
docker compose down                       # history stays in the flowlab-data volume
```

The image contains both the Python API and the built Web UI. The Compose service publishes to the
loopback interface only.

## Commands

| Command | Purpose |
|---|---|
| `flowlab demo` | Run the full pipeline on synthetic data (5,000 normal + 500 attack flows by default) |
| `flowlab run FILE` | Run an experiment on CSV / pcap / Zeek conn.log; requires a `label` column |
| `flowlab score FILE` | Rank unlabeled flows with an unsupervised model |
| `flowlab run FILE --labels L` | Attach labels to pcap flows by `flow_id`, five-tuple, or row order |
| `flowlab serve` | Start the local Web workbench |
| `flowlab sample` | Generate a sample CSV for testing or sharing |
| `flowlab formats` | List supported input formats |
| `flowlab models` | List registered models |
| `flowlab history` | Recent experiments stored in local SQLite (`~/.flowlab/flowlab.db`) |
| `flowlab history --prune 20` | Keep only the 20 most recent runs |
| `flowlab show ID` | Inspect a run and export Markdown / HTML |
| `flowlab compare ID1 ID2` | Compare best metrics across runs |

Shared flags: `--models mlp,iforest`, `--split temporal|random|group`, `--test-size`,
`--validation-size`, `--threshold-mode fixed|f1`, `--threshold`, `--seed`,
`--ablate COLUMN` (drop one column and rerun to quantify its contribution),
`--html PATH` (standalone HTML), `--report PATH` (Markdown), `--json`, `--no-save`.

## Project site and CI

- **Quality**: Ruff checks and format validation; the full backend suite on Python 3.11 and 3.13
- **Frontend**: component tests, a full dependency audit, and a production build
- **Packaging**: verifies both a source checkout without frontend assets and a release wheel with the embedded Web UI
- **Container**: builds the Docker image on every CI run
- **Pages**: deploys the Chinese and English project sites plus a static sample report generated from synthetic data
- **Local workbench**: GitHub Pages hosts the introduction only; the full Web UI needs the local Python backend (`flowlab serve`)

## Highlights in v0.8

- **Cross-experiment comparison**: select 2–4 runs and validate the dataset fingerprint, feature matrix, split, validation size, and threshold policy before comparing validation/test metrics and deltas; export the table as Markdown.
- **History workflow**: search by source, model, status, or note; browse pages; annotate runs as baseline/failed/archived; delete one run or prune older history by retention count.
- **Data quality**: report label coverage, duplicate rows, multi-label entity conflicts, and tiny classes separately from model performance.
- **Diagnostics**: target-FPR threshold selection, ROC/PR curves, calibration curves, Brier score, and a model-parameter table.
- **Reproducible environment**: reports record FlowLab, Python, pandas, NumPy, and scikit-learn versions; the environment is part of the experiment fingerprint.
- **Interface and security**: narrow-screen history/comparison dialogs, a collapsed checklist by default, and a host allowlist plus security headers for the local API.

See the [optimization roadmap](docs/OPTIMIZATION-ROADMAP.md) for the next priorities and acceptance criteria.

## Architecture

```
CSV / pcap
   ↓ ingest        normalize columns, sniff delimiters/encoding, aggregate five-tuples
   ↓ features      leakage checks → preprocessors fitted on the training split only
   ↓ models        plugin registry (mlp / iforest / autoencoder / your model)
   ↓ eval          temporal/random/group split → validation model selection → test metrics, diagnostics, label quality, investigation
   ↓ report/api    fingerprint, runtime environment, seed, feature list, class distribution, confusion matrix, rerun command
  ↓ store          local SQLite experiment history (never uploaded)
```

Shared loading pipeline for CLI and API:

```
read file → normalize columns → attach labels (optional) → feature engineering (1 ms rate floor, bytes_per_pkt)
```

Adding a model takes one file. Any module placed under `src/flowlab/models/` is discovered automatically:

```python
from flowlab.models.base import Detector
from flowlab.models.registry import register


@register("your_model")
class YourDetector(Detector):
    kind = "supervised"

    def fit(self, X, y): ...
    def score(self, X): ...  # return [0, 1]; higher means more suspicious
```

## What this project solves

Researchers in traffic anomaly detection spend most of their time not on models, but on finding datasets,
writing preprocessing code, aligning features, and reproducing someone else's F1.
Security operators, meanwhile, receive a rule alert or a single score without a clear answer to
"why is this suspicious, and what should I do next?"

The missing layer is the one that **puts a model into a system, turns results into an explanation,
and makes the experiment reproducible**.

## Documentation

The design documents are currently written in Chinese.

| File | Purpose |
|---|---|
| `01-问题陈述.md` | Problem statement, users, and evidence |
| `02-用户画像与场景.md` | User personas, JTBD, and alternatives |
| `03-竞品快照.md` | Competitive snapshot and gap analysis |
| `04-PRD.md` | Goals, non-goals, user stories, and acceptance criteria |
| `05-MVP范围与里程碑.md` | MVP scope and milestone plan |
| `06-验证实验-PoL-Probe.md` | Three-day demand-validation probe |
| `07-技术架构与数据流.md` | Technical architecture and data flow |
| `08-指标与成功标准.md` | Success metrics and instrumentation plan |
| `09-开放问题.md` | Open decisions |
| `docs/OPTIMIZATION-ROADMAP.md` | Prioritized next steps and acceptance criteria |
| `CHANGELOG.md` | Version history |
| `CONTRIBUTING.md` | Local development, testing, and contribution rules |
| `SECURITY.md` | Trust boundaries and vulnerability reporting |

## Established facts

- Open-source projects are mature at the **collection layer** (Zeek/Suricata/nDPI/ntopng) and the **algorithm layer** (Kitsune/Slips/paper code).
- A GitHub search for `ml nids platform` surfaced very little work connecting models to systems.
- Available assets include SPIN-OW models and baselines (ISCX-APP / ISCX-SERVICE / ISCX-TOR / USTC-2016), a workstation with 22 GB of VRAM, and local deployment experience.

## Decisions (2026-11-11)

| Decision | Result |
|---|---|
| Primary user | **Security researchers** (Persona A); teachers and small teams are secondary |
| License | **Apache-2.0** |
| SPIN-OW weights | **Not bundled**; an integration template is provided |
| Input formats | **CSV and pcap** (pcap currently parsed offline with tshark; nDPI is a possible extension) |
| Project execution | Milestone-driven; decisions and acceptance happen at key checkpoints |

## Three principles

1. **Work with Zeek/Suricata, not against them** — treat their output as input.
2. **Reproducibility before real-time** — researchers care about reproducing results, not line-rate throughput.
3. **Every feature must answer "which user would spend another 30 minutes on this?"** — otherwise, cut it.
