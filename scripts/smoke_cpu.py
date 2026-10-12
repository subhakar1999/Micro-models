"""Real inference smoke checks. --asr-download fetches the publisher's test audio and tiny.en weights."""
import argparse
import json
import os
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from micro_models.api import create_app
from micro_models.config import Settings


def make_pdf(path):
    # A small, valid born-digital fixture using a built-in PDF font.
    stream = b"BT /F1 18 Tf 50 750 Td (Invoice Number: INV-123) Tj 0 -30 Td (Total: 49.95) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for i, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["text", "asr", "document", "tts"], required=True)
    parser.add_argument("--asr-download", action="store_true")
    args = parser.parse_args()
    work = Path("artifacts")
    work.mkdir(exist_ok=True)
    os.environ.setdefault("HF_HOME", str(Path("models/hf-cache").resolve()))
    settings = Settings(task=args.task, profile_path=Path(f"profiles/{args.task}.json"),
                        data_dir=work / f"smoke-{args.task}", text_backend="gguf", threads=2)
    client = TestClient(create_app(settings))
    start = time.perf_counter()
    if args.task == "text":
        response = client.post("/v1/text", json={"prompt": "What is 2 plus 2? Answer with only the number.",
                                                "max_tokens": 16})
    elif args.task == "document":
        fixture = work / "invoice.pdf"
        make_pdf(fixture)
        with fixture.open("rb") as file:
            response = client.post("/v1/document", files={"file": (fixture.name, file)})
    elif args.task == "asr":
        fixture = work / "jfk.flac"
        if args.asr_download:
            audio = httpx.get("https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/tests/data/jfk.flac",
                              follow_redirects=True, timeout=60)
            audio.raise_for_status()
            fixture.write_bytes(audio.content)
        if not fixture.is_file():
            parser.error("First run with --asr-download or supply artifacts/jfk.flac")
        with fixture.open("rb") as file:
            response = client.post("/v1/asr", files={"file": (fixture.name, file)})
    else:
        response = client.post("/v1/tts", json={"text": "Hello. This is the English micro model service."})
        if response.status_code == 200:
            (work / "speech.wav").write_bytes(response.content)
    result = response.json() if "json" in response.headers.get("content-type", "") else {"bytes": len(response.content)}
    report = {"task": args.task, "status_code": response.status_code,
              "elapsed_seconds": round(time.perf_counter() - start, 3),
              "health": client.get("/health").json(), "result": result}
    (work / f"smoke-{args.task}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    response.raise_for_status()
    if args.task == "text":
        assert result["text"].strip() == "4", "Text sanity check failed"
        schema = {"type": "object", "properties": {"total": {"type": "number"}},
                  "required": ["total"], "additionalProperties": False}
        structured = client.post("/v1/text", json={"prompt": "Invoice total is 49.95. Extract the total.",
                                                  "max_tokens": 64, "schema": schema})
        structured.raise_for_status()
        parsed = json.loads(structured.json()["text"])
        assert parsed == {"total": 49.95}, "Structured extraction check failed"
        report["structured_result"] = structured.json()
        (work / "smoke-text.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    elif args.task == "document":
        assert result["fields"]["invoice_number"] == "INV-123"
        assert result["fields"]["total"] == "49.95"
    elif args.task == "asr":
        assert "country" in result["text"].lower(), "Speech sanity check failed"
    else:
        assert response.content[:4] == b"RIFF", "Invalid WAV output"


if __name__ == "__main__":
    main()
