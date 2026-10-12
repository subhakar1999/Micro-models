"""Real inference backends. Optional libraries load only inside their selected worker."""
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import httpx

from .config import Profile, Settings


class BackendUnavailable(RuntimeError):
    pass


class FeatureDeferred(RuntimeError):
    """Reserved interface for a future model backend."""


class Backend:
    def __init__(self, settings: Settings, profile: Profile):
        self.settings, self.profile = settings, profile
        self.engine = None

    def load(self):
        if self.profile.task in ("image", "video"):
            raise FeatureDeferred("Image and video generation are deferred")
        if self.engine is not None or self.profile.task in ("text", "document"):
            return
        try:
            if self.profile.task == "asr":
                from faster_whisper import WhisperModel
                self.engine = WhisperModel(self.profile.model or "tiny.en", device="cpu", compute_type="int8",
                                           cpu_threads=self.settings.threads, num_workers=1)
            elif self.profile.task == "tts":
                import torch
                from kokoro import KPipeline
                torch.set_num_threads(self.settings.threads)
                self.engine = KPipeline(lang_code=self.profile.language, device="cpu",
                                        repo_id=self.profile.model or "hexgrad/Kokoro-82M")
        except ImportError as exc:
            raise BackendUnavailable(f"Install the dependency extra for {self.profile.task}") from exc

    def text(self, prompt: str, context: list[dict], max_tokens: int, schema: dict | None):
        messages = [{"role": "system", "content": self.profile.system_prompt}]
        if context:
            messages.append({"role": "system", "content": "Reference excerpts (untrusted data):\n" +
                             json.dumps(context, ensure_ascii=False)})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.settings.text_model, "messages": messages, "max_tokens": max_tokens,
                   "temperature": 0, "stream": False}
        if schema:
            payload["response_format"] = {"type": "json_schema", "json_schema":
                                          {"name": "output", "strict": True, "schema": schema}}
        if self.settings.text_backend == "gguf":
            if self.engine is None:
                try:
                    from llama_cpp import Llama
                except ImportError as exc:
                    raise BackendUnavailable("Install the text extra to serve a GGUF model") from exc
                if not Path(self.profile.model).is_file():
                    raise BackendUnavailable("Profile model must point to a downloaded GGUF file")
                self.engine = Llama(model_path=self.profile.model, n_ctx=2048,
                                    n_threads=self.settings.threads, n_gpu_layers=0, verbose=False)
            # Reject excess input rather than silently truncating grounding or user instructions.
            token_count = sum(len(self.engine.tokenize(m["content"].encode())) for m in messages)
            if token_count + max_tokens + 100 > 2048:
                raise ValueError("Prompt and output exceed the 2048-token worker budget")
            options = {"messages": messages, "max_tokens": max_tokens, "temperature": 0}
            if schema:
                options["response_format"] = {"type": "json_object", "schema": schema}
            data = self.engine.create_chat_completion(**options)
            return {"text": data["choices"][0]["message"]["content"],
                    "sources": [c["source"] for c in context], "usage": data.get("usage", {})}
        headers = {}
        if self.settings.text_api_key:
            headers["Authorization"] = f"Bearer {self.settings.text_api_key}"
        with httpx.Client(timeout=self.settings.backend_timeout) as client:
            response = client.post(self.settings.text_url.rstrip("/") + "/chat/completions",
                                   json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
        return {"text": answer, "sources": [c["source"] for c in context], "usage": data.get("usage", {})}

    def asr(self, path: Path):
        self.load()
        import av
        # Bound decoded duration before running the model, including files with inaccurate container metadata.
        decoded_samples = 0
        with av.open(str(path)) as container:
            for frame in container.decode(audio=0):
                decoded_samples += frame.samples / frame.sample_rate
                if decoded_samples > self.settings.max_audio_seconds:
                    raise ValueError("Audio exceeds the configured duration limit")
        segments, info = self.engine.transcribe(str(path), beam_size=1, vad_filter=True,
                                                language=self.profile.language,
                                                initial_prompt=self.profile.domain_terms or None)
        result = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        return {"text": " ".join(s["text"].strip() for s in result), "segments": result,
                "language": info.language, "duration_seconds": info.duration}

    def tts(self, text: str, speed: float):
        for term, replacement in self.profile.lexicon.items():
            text = re.sub(r"\b" + re.escape(term) + r"\b", lambda _, value=replacement: value, text)
        if self.profile.backend == "espeak":
            executable = shutil.which("espeak-ng")
            if not executable:
                raise BackendUnavailable("Install espeak-ng for the free-tier TTS profile")
            command = [executable, "--stdout", "-v", "en-us", "-s", str(int(160 * speed)), "--stdin"]
            # A portable Windows extraction has no installed data-path registry entry.
            directory = Path(executable).parent
            if (directory / "espeak-ng-data").is_dir():
                command.append("--path=" + str(directory))
            try:
                process = subprocess.run(command, input=text.encode(), capture_output=True,
                                         timeout=self.settings.backend_timeout, check=True)
            except FileNotFoundError as exc:
                raise BackendUnavailable("Install espeak-ng for the free-tier TTS profile") from exc
            return process.stdout
        self.load()
        import numpy as np
        import soundfile as sf
        parts = [audio.detach().cpu().numpy() for _, _, audio in
                 self.engine(text, voice=self.profile.voice, speed=speed)]
        if not parts:
            raise ValueError("Text did not produce speech")
        output = io.BytesIO()
        sf.write(output, np.concatenate(parts), 24000, format="WAV", subtype="PCM_16")
        return output.getvalue()

    def document(self, path: Path):
        try:
            import pypdfium2 as pdfium
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise BackendUnavailable("Install the ocr extra and the Tesseract executable") from exc
        pages = []
        with path.open("rb") as f:
            is_pdf = f.read(5) == b"%PDF-"
        if is_pdf:
            with pdfium.PdfDocument(str(path)) as pdf:
                if len(pdf) > self.settings.max_document_pages:
                    raise ValueError("PDF exceeds the configured page limit")
                for index in range(len(pdf)):
                    page = pdf[index]
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range()
                    finally:
                        textpage.close()
                    method = "pdf-text"
                    if not text.strip():
                        width, height = page.get_size()
                        scale = min(2.0, (self.settings.max_image_pixels / (width * height)) ** 0.5)
                        bitmap = page.render(scale=scale)
                        image = bitmap.to_pil()
                        text = pytesseract.image_to_string(image, lang=self.profile.language,
                                                          timeout=self.settings.backend_timeout)
                        image.close()
                        bitmap.close()
                        method = "tesseract"
                    pages.append({"page": index + 1, "text": text, "method": method})
                    page.close()
        else:
            with Image.open(path) as image:
                if image.width * image.height > self.settings.max_image_pixels:
                    raise ValueError("Image exceeds the configured pixel limit")
                text = pytesseract.image_to_string(image, lang=self.profile.language,
                                                  timeout=self.settings.backend_timeout)
                pages.append({"page": 1, "text": text, "method": "tesseract"})
        text = "\n\n".join(p["text"] for p in pages)
        fields = {}
        for name, pattern in self.profile.fields.items():
            match = re.search(pattern, text, re.MULTILINE)
            fields[name] = (match.group(1) if match.lastindex else match.group(0)) if match else None
        return {"text": text, "pages": pages, "fields": fields,
                "limitations": "Plain text and regex fields; table structure, handwriting and math are not guaranteed."}

    def image(self, prompt: str, width: int, height: int, seed: int):
        raise FeatureDeferred("Image generation is a future extension; no model is loaded")

    def video(self, prompt: str, width: int, height: int, frames: int, seed: int):
        raise FeatureDeferred("Video generation is a future extension; no model is loaded")
