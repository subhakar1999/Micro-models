import hmac
import logging
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import httpx
import psutil
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from starlette.background import BackgroundTask

from .backends import Backend, BackendUnavailable, FeatureDeferred
from .config import Settings
from .limits import BodyLimitMiddleware
from .memory import Memory

logger = logging.getLogger(__name__)


class TextRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=6000)
    tenant: str = Field(default="default", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    max_tokens: int = Field(default=128, ge=1, le=512)
    schema_: dict | None = Field(default=None, alias="schema")


class IngestRequest(BaseModel):
    tenant: str = Field(default="default", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    source: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=100_000)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    speed: float = Field(default=1, ge=0.5, le=2)


class RenderRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    width: int = Field(default=512, ge=256, le=1024)
    height: int = Field(default=512, ge=256, le=1024)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    frames: int = Field(default=33, ge=9, le=65)

    @model_validator(mode="after")
    def dimensions(self):
        if self.width % 32 or self.height % 32 or (self.frames - 1) % 8:
            raise ValueError("Dimensions must be multiples of 32; frames must be 8n+1")
        return self


def create_app(settings: Settings | None = None, backend=None):
    settings = settings or Settings.from_env()
    profile = settings.profile()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = backend or Backend(settings, profile)
    memory = Memory(settings.data_dir / "memory.sqlite") if settings.task == "text" else None
    lock = threading.Lock()
    app = FastAPI(title=f"Micro-model: {settings.task}", version="0.1.0")
    app.add_middleware(BodyLimitMiddleware, maximum=settings.max_upload_bytes + 65536)
    app.state.engine = engine

    def authorized(authorization: str | None = Header(default=None)):
        if settings.api_key and not hmac.compare_digest(authorization or "", "Bearer " + settings.api_key):
            raise HTTPException(401, "Invalid API key")

    @contextmanager
    def inference(task: str):
        if task != settings.task:
            raise HTTPException(404, f"This worker serves {settings.task}")
        if not lock.acquire(blocking=False):
            raise HTTPException(429, "Worker is busy; retry later", headers={"Retry-After": "2"})
        try:
            yield
        except FeatureDeferred as exc:
            raise HTTPException(501, str(exc)) from exc
        except BackendUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.warning("Text server unavailable: %s", type(exc).__name__)
            raise HTTPException(503, "Configured text server is unavailable") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Inference failed")
            raise HTTPException(503, "Inference failed; see worker logs") from exc
        finally:
            lock.release()

    async def save_upload(upload: UploadFile):
        size = 0
        path = None
        try:
            with tempfile.NamedTemporaryFile(dir=settings.data_dir, delete=False) as temporary:
                path = Path(temporary.name)
                while block := await upload.read(65536):
                    size += len(block)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "File exceeds upload limit")
                    temporary.write(block)
            if not size:
                raise HTTPException(422, "Empty upload")
            return path
        except BaseException:
            if path:
                path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    @app.get("/health")
    def health():
        return {"status": "alive", "task": settings.task,
                "implemented": settings.task not in ("image", "video"),
                "model_loaded": engine.engine is not None, "busy": lock.locked(),
                "rss_mb": round(psutil.Process().memory_info().rss / 1024**2, 1)}

    @app.post("/v1/text", dependencies=[Depends(authorized)])
    def text(request: TextRequest):
        start = time.perf_counter()
        with inference("text"):
            result = engine.text(request.prompt, memory.search(request.tenant, request.prompt),
                                 request.max_tokens, request.schema_)
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result

    @app.post("/v1/memory", dependencies=[Depends(authorized)])
    def ingest(request: IngestRequest):
        if settings.task != "text":
            raise HTTPException(404, "Memory belongs to the text worker")
        return {"chunks": memory.ingest(request.tenant, request.source, request.text)}

    @app.post("/v1/asr", dependencies=[Depends(authorized)])
    async def asr(file: Annotated[UploadFile, File()]):
        if settings.task != "asr":
            raise HTTPException(404, "This worker does not serve asr")
        path = await save_upload(file)
        try:
            from starlette.concurrency import run_in_threadpool
            def run():
                with inference("asr"):
                    return engine.asr(path)
            return await run_in_threadpool(run)
        finally:
            path.unlink(missing_ok=True)

    @app.post("/v1/document", dependencies=[Depends(authorized)])
    async def document(file: Annotated[UploadFile, File()]):
        if settings.task != "document":
            raise HTTPException(404, "This worker does not serve documents")
        path = await save_upload(file)
        try:
            from starlette.concurrency import run_in_threadpool
            def run():
                with inference("document"):
                    return engine.document(path)
            return await run_in_threadpool(run)
        finally:
            path.unlink(missing_ok=True)

    @app.post("/v1/tts", dependencies=[Depends(authorized)])
    def tts(request: SpeechRequest):
        with inference("tts"):
            return Response(engine.tts(request.text, request.speed), media_type="audio/wav")

    @app.post("/v1/image", dependencies=[Depends(authorized)])
    def image(request: RenderRequest):
        with inference("image"):
            return Response(engine.image(request.prompt, request.width, request.height, request.seed),
                            media_type="image/png")

    @app.post("/v1/video", dependencies=[Depends(authorized)])
    def video(request: RenderRequest):
        with inference("video"):
            if request.width * request.height > 512 * 768:
                raise HTTPException(422, "Video pixel budget exceeds 512x768")
            output = engine.video(request.prompt, request.width, request.height, request.frames, request.seed)
            return FileResponse(output, media_type="video/mp4", filename="video.mp4",
                                background=BackgroundTask(output.unlink, missing_ok=True))

    return app
