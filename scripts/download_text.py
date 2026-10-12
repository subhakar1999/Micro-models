"""Download the publisher's GGUF; no model surgery is implied by downloading it."""
import argparse
from pathlib import Path

import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("models/qwen2.5-0.5b-instruct-q4_k_m.gguf"))
args = parser.parse_args()
url = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
args.output.parent.mkdir(parents=True, exist_ok=True)
temporary = args.output.with_suffix(".partial")
try:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open("wb") as file:
            for block in response.iter_bytes():
                file.write(block)
    with temporary.open("rb") as file:
        if file.read(4) != b"GGUF":
            raise ValueError("Downloaded file is not a GGUF model")
    temporary.replace(args.output)
finally:
    temporary.unlink(missing_ok=True)
print(args.output)
