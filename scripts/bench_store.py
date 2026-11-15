"""历史库基准：压缩 payload、页面查询和单条读取的本机耗时。"""

from __future__ import annotations

import argparse
import os
import statistics
import tempfile
import time
from pathlib import Path

from flowlab import store


def _payload(index: int) -> dict:
    markdown_rows = "\n".join(
        f"| flow-{index}-{row} | 10.0.{(row * 37) % 255}.{(index + row) % 255} "
        f"| {row * 7919 % 100_000} | {row * 104_729 % 1_000_003} |"
        for row in range(500)
    )
    markdown = f"# FlowLab synthetic report {index}\n\n{markdown_rows}\n"
    html = (
        "<html><body><table>"
        + "".join(
            f"<tr><td>flow-{index}-{row}</td><td>10.0.{(row * 37) % 255}.{(index + row) % 255}</td>"
            f"<td>{row * 7919 % 100_000}</td><td>{row * 104_729 % 1_000_003}</td></tr>"
            for row in range(500)
        )
        + "</table></body></html>"
    )
    return {
        "dataset": {
            "source": f"synthetic-{index}.csv",
            "hash": f"hash-{index:05d}",
            "split": "temporal",
            "seed": 42,
            "threshold": 0.5,
            "rows": 50_000,
            "train": 25_000,
            "validation": 10_000,
            "test": 15_000,
        },
        "experiment_fingerprint": f"fingerprint-{index:05d}",
        "best_model": "iforest",
        "results": [
            {
                "model": "iforest",
                "metrics": {"auc": 0.95, "pr_auc": 0.87, "f1": 0.82, "attack_support": 5_000},
                "validation_metrics": {"auc": 0.94},
                "duration_s": 2.1,
            }
        ],
        "top_flows": [{"src_ip": f"10.0.0.{j % 255}", "score": 0.9} for j in range(20)],
        "report_md": markdown,
        "report_html": html,
    }


def _ms(fn):
    start = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--queries", type=int, default=30)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="flowlab-store-bench-") as home:
        os.environ["FLOWLAB_HOME"] = home
        ids = []
        save_times = []
        for index in range(args.runs):
            run_id, elapsed = _ms(lambda index=index: store.save_run(_payload(index)))
            ids.append(run_id)
            save_times.append(elapsed)

        capacity = store.stats()
        page_times = []
        for _ in range(args.queries):
            _, elapsed = _ms(
                lambda: store.history_page(limit=30, offset=0, query="synthetic", status=None)
            )
            page_times.append(elapsed)

        load_times = []
        for run_id in ids[-min(30, len(ids)) :]:
            _, elapsed = _ms(lambda run_id=run_id: store.get_run(run_id))
            load_times.append(elapsed)

        path = Path(home) / "flowlab.db"
        ratio = (
            capacity["payload_bytes"] / capacity["payload_raw_bytes"]
            if capacity["payload_raw_bytes"]
            else 0
        )
        print(f"runs                 {args.runs:8d}")
        print(f"db_bytes             {path.stat().st_size / 2**20:8.2f} MB")
        print(f"wal_bytes            {capacity['wal_bytes'] / 2**20:8.2f} MB")
        print(f"payload raw          {capacity['payload_raw_bytes'] / 2**20:8.2f} MB")
        print(f"payload stored       {capacity['payload_bytes'] / 2**20:8.2f} MB")
        print(f"compression ratio    {ratio:8.2%}")
        print(f"save p50             {statistics.median(save_times):8.2f} ms")
        print(f"history page p50     {statistics.median(page_times):8.2f} ms")
        print(f"load payload p50     {statistics.median(load_times):8.2f} ms")


if __name__ == "__main__":
    main()
