# Validation in this workspace

Tests ran locally on Windows with Python 3.11.15. No Google Cloud resources were created, and the local Docker daemon was unavailable. Container builds and Cloud Run deployment have therefore **not** been exercised here. The measurements below are single smoke tests, not throughput benchmarks or cloud guarantees.

| Real backend check | Observed result |
| --- | --- |
| Publisher Qwen2.5-0.5B Q4_K_M | Loaded the 491,400,032-byte GGUF; answered arithmetic with `4`; process RSS about 565 MB after inference |
| Constrained JSON | Extracted `{"total":49.95}` using a JSON-schema grammar |
| Whisper tiny.en INT8 | Transcribed an 11-second English test clip; cached-model smoke took about 1.1 seconds including model load; process RSS about 204 MB |
| Born-digital PDF | Extracted `INV-123` and `49.95` from a valid one-page PDF; process RSS about 66 MB |
| eSpeak NG 1.51 portable Windows | Produced a 150,598-byte RIFF/WAV file; Python process RSS about 53 MB, excluding the native child process |
| Image and video | Both reserved workers return HTTP 501 and do not load models |

Reports are in `artifacts/smoke-*.json`; the actual GGUF metadata is in `artifacts/gguf-inspection.json`. eSpeak 1.52's extracted Windows executable crashed locally, so the successful synthesis check used the official 1.51 x64 build with an explicit portable data path. The Linux container installs Debian's eSpeak package and still needs its own smoke test.

API tests cover authentication, retrieval tenant separation, replacement of source chunks, upload and request-body limits (including chunked bodies), file cleanup, request validation, concurrency rejection, failure recovery, text-server contracts, missing model errors, and deferred image/video paths. Formatting/static checks use Ruff; Python files are compiled for syntax errors.

Offline customization tests use a random four-layer Qwen2 fixture: block-influence calibration, physically pruned checkpoint save/reload, cached generation after pruning, a rejecting perplexity gate, assistant-only LoRA training and merged checkpoint reload. This validates the utility mechanics, not the quality of a real pruned or domain-trained model. Testing found and fixed the need to prune Qwen2's per-layer configuration metadata along with its tensors.

Scanned-image OCR and Kokoro natural speech were not exercised. The PDF smoke only covers PDFium text extraction and field rules. Multi-user authorization, persistent Cloud Run memory, stream processing, multi-LoRA batching and domain-trained model accuracy are not claimed. Training example files demonstrate format only; no domain-trained weights have been produced.

Before cloud deployment, run the selected container's real smoke test and measure native process **peak** memory. Keep the text context, uploads, page counts and output tokens bounded. Measure task accuracy on the intended domain and languages rather than extrapolating from the tiny sanity fixtures.
# Combined UI validation (2026-10-12)

The combined server was tested through live HTTP requests for text answers,
PDF text extraction, printed-image OCR with Tesseract, English audio transcription,
and Kokoro natural-voice WAV generation. All returned successful responses.
The generated Kokoro sample was a mono, 24 kHz WAV; this verifies generation,
not a listening-based quality score. The beginner website was served separately
on port 5500 and returned HTTP 200. Its JavaScript passed a syntax check.
The automated suite passed 17 tests, including browser-origin and API-key checks.

Earlier development notes follow.

