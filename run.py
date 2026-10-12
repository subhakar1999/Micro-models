"""Start a selected English CPU service from the project directory."""
import argparse
import os
from pathlib import Path

import uvicorn

from micro_models.api import create_app
from micro_models.config import Settings

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", choices=["text", "asr", "tts", "document", "image", "video"], default="text")
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
parser.add_argument("--profile", type=Path)
parser.add_argument("--text-backend", choices=["gguf", "http"], default="gguf")
args = parser.parse_args()
settings = Settings.from_env().model_copy(update={"task": args.task,
           "profile_path": args.profile or Path(f"profiles/{args.task}.json"),
           "data_dir": Path("data") / args.task, "text_backend": args.text_backend})
uvicorn.run(create_app(settings), host="0.0.0.0", port=args.port, workers=1)
