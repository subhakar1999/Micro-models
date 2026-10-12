FROM python:3.11-slim AS wheels
ARG EXTRA=ocr
WORKDIR /build
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF"
COPY pyproject.toml ./
COPY micro_models ./micro_models
# Compile llama.cpp only when EXTRA=text. Build tools stay out of the runtime.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake && rm -rf /var/lib/apt/lists/*
RUN pip wheel --wheel-dir=/wheels ".[${EXTRA}]"

FROM python:3.11-slim
ARG EXTRA=ocr
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
    MICRO_THREADS=1 MICRO_DATA_DIR=/tmp/micro-data HF_HOME=/opt/hf PORT=8080
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 espeak-ng tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY --from=wheels /wheels /wheels
RUN pip install --no-index --find-links=/wheels "micro-models[${EXTRA}]" && rm -rf /wheels
WORKDIR /app
COPY profiles ./profiles
COPY scripts/download_text.py ./scripts/download_text.py
# Weights are baked in for text; ASR is pre-fetched to avoid startup downloads.
RUN if [ "$EXTRA" = "text" ]; then python scripts/download_text.py; fi
RUN if [ "$EXTRA" = "asr" ]; then python -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"; fi
RUN useradd --create-home --uid 10001 micro && mkdir -p /opt/hf && chmod -R a+rX /app /opt/hf
ENV HF_HUB_OFFLINE=1
USER micro
EXPOSE 8080
CMD ["python", "-m", "micro_models"]
