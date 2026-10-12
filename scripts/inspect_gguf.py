"""Inspect the deployed checkpoint metadata without downloading float training weights."""
import argparse
import json
from pathlib import Path

from llama_cpp import Llama

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", type=Path, default=Path("models/qwen2.5-0.5b-instruct-q4_k_m.gguf"))
parser.add_argument("--output", type=Path, default=Path("artifacts/gguf-inspection.json"))
args = parser.parse_args()
model = Llama(model_path=str(args.model), n_ctx=256, n_threads=1, n_gpu_layers=0, verbose=False)
report = {"checkpoint": str(args.model), "file_bytes": args.model.stat().st_size,
          "metadata": model.metadata, "inspection_context_tokens": model.n_ctx(),
          "vocabulary_size": model.n_vocab(), "note": "Disk bytes are not runtime RAM; use inference benchmarks."}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in report.items() if key != "metadata"}, indent=2))
model.close()
