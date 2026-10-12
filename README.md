# Micro-models

Small Python services for **English text, speech and documents on a CPU**. Run only the service you need to keep memory and compute usage low.

The target is low-volume Google Cloud use within a free-tier budget. Image and video generation are placeholders for future development.

## What does it do?

| Service | Input | Output | Technology |
| --- | --- | --- | --- |
| Text | A question or instruction | An answer or structured JSON | Quantized Qwen2.5-0.5B |
| Speech recognition | English audio | Transcript and timestamps | Whisper tiny.en, INT8 |
| Speech synthesis | English text | WAV audio | eSpeak NG |
| Documents | PDF or scanned image | Text and configured fields | PDFium + Tesseract |
| Image / video | Reserved request | HTTP 501: not implemented | Future extension |

**Customization:** edit configuration files to change instructions, speech terminology, pronunciations and document fields. The baseline uses existing pretrained models. Training tools are included, but useful domain-trained weights require your own examples and evaluation data.

The default speech voice is robotic because it prioritizes low compute. Kokoro is an optional natural-voice backend with larger dependencies. Document extraction provides text and configured fields; advanced tables, handwriting and mathematical notation may need stronger models later.

## Quick start in this existing workspace

For a browser UI with document upload, document questions, text generation,
transcription and speech playback, run:

```powershell
.venv\Scripts\python.exe run_ui.py
```

Open **http://localhost:8080**. In **Documents & questions**, upload a document
and wait for it to be prepared, then enter your question. The UI automatically
stores extracted text for that document's questions. Speech downloads its model
on first use; scanned documents require Tesseract. The launcher detects the
portable eSpeak executable in this workspace. Models stay loaded after use, so
this combined UI can use more memory than running one worker. Press **Ctrl+C**
to stop it. Use `--port 8081` if port 8080 is occupied.

The UI uses the natural Kokoro voice by default. Install it with
`uv pip install --python .venv\Scripts\python.exe -e '.[tts]'`.
Its model downloads on first use and uses more memory than eSpeak.
Use `run_ui.py --speech-quality fast` for the lightweight robotic eSpeak voice.

Use **Connect your app** to configure a service base URL and get the JavaScript
client. See [app integration](docs/app-integration.md) for browser origins,
hosted HTTPS connections and document question examples.

The Python environment and text model were prepared during development.

Open **PowerShell** in `F:\Projects\Micro-models` and run:

```powershell
.venv\Scripts\python.exe run.py --task text
```

Keep the terminal open. Visit **http://localhost:8000/docs** in your browser.

1. Open **POST /v1/text**.
2. Click **Try it out**.
3. Enter the request below and click **Execute**.

```json
{
  "prompt": "What is 2 plus 2? Answer briefly.",
  "max_tokens": 32
}
```

Look for the answer in the response's `text` field. Press **Ctrl+C** in PowerShell to stop the service.

**Installing a fresh copy?** Complete the next section first. Run every command from the project folder.

## Install a fresh copy

### 1. Create the Python environment

You need PowerShell, [uv](https://docs.astral.sh/uv/) and internet access for downloads. These commands let uv install Python:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.python"
uv python install 3.11
uv venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -e '.[dev,asr,ocr]'
```

### 2. Install text inference and download the model

```powershell
uv pip install --python .venv\Scripts\python.exe llama-cpp-python --only-binary=:all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
.venv\Scripts\python.exe scripts\download_text.py
```

The tested model file is approximately **491 MB** and goes into `models/`. You download it once. Local text inference does not call a paid AI API.

If no compatible wheel is available for your computer, follow the [llama-cpp-python installation instructions](https://github.com/abetlen/llama-cpp-python). Building from source requires a C++ compiler and CMake.

### 3. Install native speech/OCR tools when needed

- Speech synthesis needs `espeak-ng` on your PATH.
- Scanned-document OCR needs `tesseract` on your PATH, with English language data.
- PDFs that already contain selectable text use PDFium directly.

See [eSpeak NG](https://github.com/espeak-ng/espeak-ng) and [Tesseract](https://github.com/tesseract-ocr/tesseract) for installation information. On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y espeak-ng tesseract-ocr tesseract-ocr-eng
```

The Docker image also installs these tools.

## Run the service you need

Choose **one** command below. On a small machine, stop it with **Ctrl+C** before starting another.

```powershell
# Questions, answers and JSON
.venv\Scripts\python.exe run.py --task text

# Audio to English text
.venv\Scripts\python.exe run.py --task asr

# English text to WAV audio
.venv\Scripts\python.exe run.py --task tts

# PDF/image to text and fields
.venv\Scripts\python.exe run.py --task document
```

Each uses port **8000**. Add `--port 8001` if you deliberately run another worker on a different port.

Speech recognition downloads its small model on first use. Set this before starting ASR to keep its cache inside the project:

```powershell
$env:HF_HOME = "$PWD\models\hf-cache"
```

For speech synthesis in the **current Windows workspace**, a tested portable executable is already available:

```powershell
$env:PATH = "$PWD\artifacts\tools\espeak-1.51\eSpeak NG;" + $env:PATH
.venv\Scripts\python.exe run.py --task tts
```

That PATH shortcut applies to this workspace. Fresh installations need their own eSpeak executable.

## Try each service

Start the matching service, then open **http://localhost:8000/docs**.

| Service | Endpoint | Input in the browser |
| --- | --- | --- |
| Text | `POST /v1/text` | `{"prompt":"Explain Python in one sentence.","max_tokens":64}` |
| Speech recognition | `POST /v1/asr` | Choose an English audio file in the `file` input |
| Speech synthesis | `POST /v1/tts` | `{"text":"Hello from the micro model service.","speed":1}` |
| Documents | `POST /v1/document` | Choose a PDF or image in the `file` input |
| Service status | `GET /health` | No input |

### Call it from Python

Save this as `client_example.py`. With the text service running, execute `.venv\Scripts\python.exe client_example.py` in another terminal:

```python
import httpx

response = httpx.post(
    "http://localhost:8000/v1/text",
    json={"prompt": "What is 2 plus 2?", "max_tokens": 32},
    timeout=120,
)
response.raise_for_status()
print(response.json()["text"])
```

For a document upload, replace the request with:

```python
with open("invoice.pdf", "rb") as file:
    response = httpx.post(
        "http://localhost:8000/v1/document",
        files={"file": ("invoice.pdf", file)},
        timeout=120,
    )
response.raise_for_status()
print(response.json())
```

Keep `import httpx` at the top of the script. For speech recognition, use `/v1/asr` and an audio file.

For speech synthesis, save the response bytes:

```python
response = httpx.post(
    "http://localhost:8000/v1/tts",
    json={"text": "Hello. This is an English speech example."},
    timeout=120,
)
response.raise_for_status()
with open("speech.wav", "wb") as file:
    file.write(response.content)
```

## Customize without training

Edit the matching JSON file and restart the service:

| File | What to change |
| --- | --- |
| `profiles/text.json` | Assistant instructions and local model path |
| `profiles/asr.json` | Domain terms, such as product names or technical vocabulary |
| `profiles/tts.json` | Pronunciations and acronym expansions |
| `profiles/document.json` | Document field extraction rules |
| `profiles/tts-quality.json` | Optional Kokoro voice settings |

For example, the speech profile can expand `GCP` to `Google Cloud Platform`. Document rules currently look for an invoice number and total. Missing fields return `null`.

The text service supports `POST /v1/memory` to store reference text and retrieve relevant excerpts for answers. With `run.py`, local data is stored under `data/text/`. Cloud Run's temporary filesystem does **not** preserve this memory across instance replacement.

For weight training or layer pruning, follow [the specialization guide](docs/specialization.md). Training happens separately from lightweight serving. The files under `examples/` show dataset format; they are too small to establish useful model quality.

## Memory usage and input limits

Local smoke checks measured approximately:

| Service | Python process memory after a small request |
| --- | --- |
| Text | 565 MB |
| Speech recognition | 204 MB |
| PDF text extraction | 66 MB |
| Speech synthesis | 53 MB, excluding the native speech process |

These are **local snapshots**, not peak-memory measurements or cloud guarantees. Start cloud testing around **1 GiB for text/ASR** and **512 MiB for documents/default TTS**, then measure the selected container.

Default input limits are 10 MiB files, 60 seconds audio, eight PDF pages and 512 generated text tokens. Text context is capped at 2,048 tokens. Each worker handles one inference at a time.

## Deploy to Google Cloud

Follow [the Google Cloud guide](docs/google-cloud.md) for Docker builds and a private Cloud Run deployment that scales to zero.

Start with **one service**, measure memory and monitor account usage. Compute, image storage and networking have separate free allowances, so a zero bill cannot be guaranteed for every workload. No cloud resources have been deployed by this repository.

Image and video placeholders are excluded from the deployment recipe.

## Verify your setup

Run automated tests:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Run a real inference check without starting a server:

```powershell
.venv\Scripts\python.exe scripts\smoke_cpu.py --task text
.venv\Scripts\python.exe scripts\smoke_cpu.py --task document
.venv\Scripts\python.exe scripts\smoke_cpu.py --task asr --asr-download
.venv\Scripts\python.exe scripts\smoke_cpu.py --task tts
```

TTS still needs eSpeak on PATH. Reports are saved under `artifacts/`. To measure an already-running text service:

```powershell
.venv\Scripts\python.exe scripts\benchmark.py --task text
```

Development validation passed 15 tests and real text, transcription, PDF extraction and speech-output checks. Scanned-image OCR, optional Kokoro and cloud/container deployment still need their own environment checks. See [validation details](docs/validation.md).

## Common problems

| Problem | What to do |
| --- | --- |
| Port 8000 is in use | Stop the previous service or use `--port 8001` |
| HTTP 404 | Start the matching task; a text worker does not handle audio |
| HTTP 429 | The worker is busy; retry after its current request finishes |
| HTTP 413 | Reduce the uploaded file or request size |
| HTTP 422 | Check request format and limits; try a shorter text prompt/output |
| HTTP 503 | Read the error/logs; confirm packages, model files and native tools |
| HTTP 501 for image/video | Expected: these features are placeholders |
| Text model is missing | Run `scripts/download_text.py` and check `profiles/text.json` |
| Speech/OCR executable is missing | Add the installed executable's folder to PATH |

For local access control, set `MICRO_API_KEY` before starting the worker and send `Authorization: Bearer YOUR_KEY`. The Cloud Run recipe uses Google's IAM authentication instead. Retrieval tenant names separate stored data; they are not a complete user authorization system.

## Project files

```text
Micro-models/
├── README.md          Getting-started guide
├── run.py             Start a selected service
├── micro_models/      API, inference backends and retrieval
├── profiles/          Task configuration files
├── scripts/           Downloads, checks, inspection and training
├── tests/             Automated tests
├── models/            Downloaded weights
├── data/              Local service data
├── artifacts/         Reports and test outputs
├── examples/          Training-data format examples
├── deploy/            Cloud Run deployment script
├── Dockerfile         CPU service container build
└── docs/              Detailed technical guides
```

Further reading: [research audit](docs/research-audit.md), [model customization](docs/specialization.md), [Google Cloud deployment](docs/google-cloud.md), and [tested behavior](docs/validation.md).
