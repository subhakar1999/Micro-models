# Micro-models

## Start here: four AI helpers for your website

Imagine four helpers working behind your website:

| Helper | You give it | It gives you |
| --- | --- | --- |
| Ask | A question, like "What is 2 plus 2?" | An answer, like "4" |
| Read | A PDF or a picture of printed words | The words inside it; you can then ask about them |
| Listen | A recording of English speech | The words that were spoken |
| Speak | English words | An audio file that reads them aloud |

Your **website** has the buttons and boxes. This project is the **server**:
the program that does the work when someone clicks a button. The **service URL**
is the server's address. Your website sends requests to that address.
You do not need to train a model to try these helpers.
Image and video generation are future features, so they do not work yet.

### 1. Turn on all four helpers

In this prepared workspace, open PowerShell and paste:

```powershell
cd F:\Projects\Micro-models
.\.venv\Scripts\python.exe run_ui.py --port 8080 --allow-origin http://localhost:5500 --allow-origin http://127.0.0.1:5500
```

Keep that window open. Open **http://localhost:8080** in your browser.
One command starts all four services; you do not need a separate port for each.
The first request can take longer because a model must load.
For a fresh installation, follow **Install a fresh copy** below first, including
the text model, TTS extra, eSpeak and Tesseract setup.

### 2. Try the buttons

| Tab | What to do | What you should see or hear |
| --- | --- | --- |
| Text | Ask "What is 2 plus 2?" | An answer containing 4 |
| Documents & questions | Choose a PDF, click **Extract & prepare for questions**, then ask about its contents | An answer with its source file |
| Transcribe audio | Choose a short English recording | The spoken words as text |
| Create speech | Type "Hello! Welcome to my website." and click **Create audio** | An audio player; press play |
| Connect your app | Enter your service URL and click **Connect & check services** | The four service statuses |

Use PDFs up to 8 pages and files up to 10 MB. Audio recordings can be up to
60 seconds. Start with English and short questions. Check AI answers against
the original document because answers can be wrong. Document questions use
matching excerpts rather than reading every page into the model at once.
The UI uses Kokoro's natural voice. `--speech-quality fast` selects robotic eSpeak.

### 3. Try a small website of your own

There is a ready-made website in [ui/website-example.html](ui/website-example.html).
It has buttons for all four helpers. In a **second** PowerShell window, run:

```powershell
cd F:\Projects\Micro-models
.\.venv\Scripts\python.exe -m http.server 5500 --bind 127.0.0.1 --directory ui
```

Open **http://localhost:5500/website-example.html**. Keep both PowerShell windows
open: one runs the AI helpers, and the other runs the example website.
Open the page through this address instead of double-clicking the HTML file.
Try its question, document, recording and speech buttons.

### 4. Add a helper to your existing website

Copy [ui/client.js](ui/client.js) into your website's folder. This small file
knows how to talk to all four helpers. Add this HTML where you want a question box:

```html
<textarea id="my-question" placeholder="Ask something"></textarea>
<button id="my-ask">Ask</button>
<p id="my-answer" role="status"></p>

<script type="module">
  import { MicroModelsClient } from './client.js';

  // CHANGE THIS when your AI server gets an online HTTPS address.
  const ai = new MicroModelsClient('http://localhost:8080');
  const button = document.getElementById('my-ask');
  const answer = document.getElementById('my-answer');

  button.addEventListener('click', async () => {
    const question = document.getElementById('my-question').value.trim();
    if (!question) { answer.textContent = 'Type a question first.'; return; }
    button.disabled = true;
    answer.textContent = 'Thinking...';
    try {
      const reply = await ai.text(question);
      answer.textContent = reply.text;
    } catch (error) {
      answer.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
</script>
```

**The few things to change:**

1. Put `client.js` next to your HTML, or change the `import` path to its location.
2. Replace the service URL when you deploy the AI server.
3. Give your website permission to call the server using `--allow-origin`.
   A local React website at `http://localhost:5173`, for example, needs
   `--allow-origin http://localhost:5173` on the server command.
4. Change the button words, colors and layout to match your website.

For React or another framework, import the same client into your component and
call `ai.text(...)` in your button's click handler. The full example page shows
how to call `ai.prepareDocument(file)`, `ai.transcribe(file)` and `ai.speech(text)`.

### 5. Put your website online

You need **two online things**: your website and the AI server. Publishing the
website alone does not publish these services. Ask an adult to help with a
hosting account and deployment. A GitHub repository holds code; it does not run
the Python server.

Once your AI server has an HTTPS address, change its URL in your website:

```javascript
const ai = new MicroModelsClient('https://YOUR-AI-SERVER');
```

Start the deployed server behind HTTPS hosting with your website's real origin:

```powershell
.\.venv\Scripts\python.exe run_ui.py --host 0.0.0.0 --port 8080 --allow-origin https://YOUR-WEBSITE
```

Replace `YOUR-AI-SERVER` and `YOUR-WEBSITE` with your addresses. Your hosting must
provide HTTPS; this command serves HTTP by itself. Do not use `localhost` for
a shared online server: it means the computer of the person visiting your site.
If your service has a private API key, keep it in your website's backend
(server-side code), not in the page visitors download. Website-origin permission
does not replace authentication. See [app integration](docs/app-integration.md)
for persistent document storage and private-user access.

### Something went wrong?

| Message or problem | Simple fix |
| --- | --- |
| Connection refused | Start the AI server and keep its PowerShell window open |
| Port already in use | Open the running UI, or choose a new `--port` and update your website's service URL |
| Cannot reach the service | Check the URL, keep both servers on, and allow your website's exact origin |
| First request is slow | Wait while the model loads; fresh copies also download models |
| OCR error | Install Tesseract with English data; the launcher detects its usual Windows install folder |
| Robotic voice | Start without `--speech-quality fast` and install the TTS extra |
| Busy / 429 | Wait for the current request, then try again |

Press **Ctrl+C** in each server window when you want to stop it.

---

## Technical setup and reference

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

Standalone speech workers default to robotic eSpeak to prioritize low compute. The combined UI defaults to Kokoro's natural voice with larger dependencies. Document extraction provides text and configured fields; advanced tables, handwriting and mathematical notation may need stronger models later.

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
