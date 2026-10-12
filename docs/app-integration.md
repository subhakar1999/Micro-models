# Connect an app with one service URL

Run the workspace locally:

```powershell
.venv\Scripts\python.exe run_ui.py --port 8082
```

Open http://localhost:8082. The **Connect your app** tab lets you change the
service base URL, check service health and download the JavaScript client.
The standalone demo at `/assets/integration.html` tests the same client.

Copy `ui/client.js` into your app and import it:

```javascript
import {MicroModelsClient} from './client.js';

const ai = new MicroModelsClient('https://YOUR-SERVICE-HOST');
const answer = await ai.text('Explain Python in one sentence.');
console.log(answer.text);

const document = await ai.prepareDocument(fileInput.files[0]);
const reply = await ai.text('What is the invoice total?', {tenant: document.tenant});
console.log(reply.text);

const transcript = await ai.transcribe(audioInput.files[0]);
const wav = await ai.speech('Hello from my app.');
audioElement.src = URL.createObjectURL(wav);
// Revoke the object URL when you no longer need it.
```

The service URL is the workspace root, without `/services` or `/v1`.
Existing single-task workers from `run.py` do not implement this combined URL.

| Function | Workspace endpoint |
| --- | --- |
| Discover services | `GET /api/services` |
| Service health | `GET /services/{task}/health` |
| Text questions | `POST /services/text/v1/text` |
| Store reference text | `POST /services/text/v1/memory` |
| Document extraction | `POST /services/document/v1/document` |
| Transcription | `POST /services/asr/v1/asr` |
| Speech WAV | `POST /services/tts/v1/tts` |

## Hosted website

A hosted website requires a deployed, reachable HTTPS backend. A localhost URL
refers to each visitor's own machine. This change does not deploy a backend.
To prepare the workspace server behind your HTTPS hosting or reverse proxy:

```powershell
$env:MICRO_API_KEY = 'YOUR_PRIVATE_SERVICE_KEY'
.venv\Scripts\python.exe run_ui.py --host 0.0.0.0 --port 8080 --allow-origin https://YOUR-APP-HOST
```

Replace the placeholders. Origins contain scheme and host (and port if needed),
without paths or trailing slashes. Repeat `--allow-origin` for another website,
or set comma-separated `MICRO_ALLOWED_ORIGINS` in your deployment.
The command itself serves HTTP; HTTPS must be provided by hosting or a proxy.

Browser CORS access is allowed only for configured origins. CORS is not API
authentication. For a private API, call from your app's backend and provide the
key there using `new MicroModelsClient(url, {apiKey})`; do not publish the shared
service key in frontend source. An app backend also works without CORS.

Document question sessions store extracted text under `data/text/`. Use persistent
storage if sessions must survive deployment replacement. Tenant labels isolate
retrieval context, but do not authenticate users. Apply your app's user access
rules before offering private documents to multiple users.

This combined workspace keeps models loaded after use. Size hosting for the
combined workload rather than the repository's isolated-worker memory figures.
Natural speech requires the TTS extra and a downloaded Kokoro model. Use
`--speech-quality fast` to test routing with the lightweight eSpeak backend.
