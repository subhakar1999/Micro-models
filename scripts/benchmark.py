"""Measure actual latency and worker RSS; do not infer serving RAM from parameter counts."""
import argparse
import json
import math
import statistics
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--task", choices=["text", "asr", "tts", "document", "image", "video"], default="text")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--prompt", default="Explain what a micro model is in one sentence.")
    parser.add_argument("--requests", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark.json"))
    args = parser.parse_args()
    import os
    headers = {"Authorization": "Bearer " + os.environ["MICRO_API_KEY"]} if os.environ.get("MICRO_API_KEY") else {}
    times, sizes, memory = [], [], []
    with httpx.Client(timeout=600, headers=headers) as client:
        for _ in range(args.requests):
            start = time.perf_counter()
            if args.task in ("asr", "document"):
                if not args.file:
                    parser.error("--file is required")
                with args.file.open("rb") as file:
                    response = client.post(f"{args.url}/v1/{args.task}", files={"file": (args.file.name, file)})
            else:
                payload = {"text" if args.task == "tts" else "prompt": args.prompt}
                response = client.post(f"{args.url}/v1/{args.task}", json=payload)
            response.raise_for_status()
            times.append((time.perf_counter() - start) * 1000)
            sizes.append(len(response.content))
            health = client.get(f"{args.url}/health")
            health.raise_for_status()
            memory.append(health.json()["rss_mb"])
    warm = times[1:] or times
    ordered = sorted(warm)
    report = {"task": args.task, "requests": args.requests, "first_request_ms": times[0],
              "warm_median_ms": statistics.median(warm), "warm_p95_ms": ordered[math.ceil(len(ordered) * .95) - 1],
              "observed_rss_mb": max(memory), "rss_note": "Post-request snapshot, excludes child/server processes and transient peak",
              "response_bytes": sizes, "latencies_ms": times}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
