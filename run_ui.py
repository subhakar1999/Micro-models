"""Run the local browser workspace and lazily loaded services."""
import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from micro_models.api import create_app
from micro_models.config import Settings

ROOT = Path(__file__).resolve().parent


def create_ui(speech_quality="natural", allowed_origins=None):
    app = FastAPI(title="Micro-models workspace")
    origins = allowed_origins or []
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins,
                           allow_methods=["GET", "POST"],
                           allow_headers=["Authorization", "Content-Type"])
    app.mount("/assets", StaticFiles(directory=ROOT / "ui"), name="assets")

    @app.get("/api/services")
    def services():
        return {"services": {task: f"/services/{task}" for task in ("text", "document", "asr", "tts")},
                "speech_quality": speech_quality}

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(ROOT / "ui" / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    for task in ("text", "document", "asr", "tts"):
        settings = Settings.from_env().model_copy(update={
            "task": task, "data_dir": ROOT / "data" / task,
            "profile_path": ROOT / "profiles" / (
                "tts-quality.json" if task == "tts" and speech_quality == "natural" else f"{task}.json"
            ), "text_backend": "gguf",
        })
        app.mount(f"/services/{task}", create_app(settings))
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--speech-quality", choices=["natural", "fast"], default="natural")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="Website origin allowed browser API access; repeat for multiple sites")
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf-cache"))
    portable = ROOT / "artifacts" / "tools" / "espeak-1.51" / "eSpeak NG"
    if portable.is_dir():
        os.environ["PATH"] = str(portable) + os.pathsep + os.environ.get("PATH", "")
    tesseract = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR"
    if (tesseract / "tesseract.exe").is_file():
        os.environ["PATH"] = str(tesseract) + os.pathsep + os.environ.get("PATH", "")
    origins = args.allow_origin or [value.strip() for value in
                                  os.environ.get("MICRO_ALLOWED_ORIGINS", "").split(",") if value.strip()]
    uvicorn.run(create_ui(args.speech_quality, origins), host=args.host, port=args.port)
