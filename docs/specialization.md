# Specialize without increasing serving compute

Start with the four task profiles. English-only tiny.en avoids a multilingual speech checkpoint; recognition hints improve vocabulary bias but do not train weights. TTS lexicon entries expand product names/acronyms; they do not clone a voice. Document regexes extract schema fields from OCR/native PDF text; non-matching fields are explicitly null. Text prompts and retrieved examples customize behavior with no duplicate model copies.

For actual domain-trained text weights, provide licensed, representative JSONL records and a **separate** held-out dataset. Each line must have a `messages` array ending in an assistant answer. Files in `examples/` show the format only and are too small to establish quality. CPU inference and offline training have different hardware requirements; do training locally or on available training hardware, not inside the free-tier serving worker.

```bash
uv pip install -e '.[train]'
python scripts/specialize.py inspect --output artifacts/inspection
python scripts/specialize.py calibrate --data TRAIN.jsonl --output artifacts/calibration
python scripts/specialize.py prune --data TRAIN.jsonl --holdout HOLDOUT.jsonl \
  --scores artifacts/calibration/report.json --fraction 0.1 --output artifacts/pruned
python scripts/specialize.py train --model artifacts/pruned \
  --data TRAIN.jsonl --holdout HOLDOUT.jsonl --output artifacts/custom
python scripts/specialize.py evaluate --model artifacts/custom --data HOLDOUT.jsonl --output artifacts/evaluation
```

`inspect` reports actual unique parameter counts and tied embeddings. `calibrate` measures each block's input/output cosine change without retaining every layer's hidden states. `prune` preserves the first/last blocks, physically removes low-influence blocks, reindexes attention cache layer IDs and saves a compatible checkpoint only if the held-out perplexity ratio passes the default 1.15 limit. It is an experimental optimization; shape compatibility does not establish task quality.

`train` uses rank-eight attention LoRA and masks prompt tokens so only the final assistant response contributes to training loss. The adapter is merged into a standalone checkpoint for simpler CPU serving. Its report flags holdout regression; a failed candidate may be saved for inspection and must not be deployed. Training and holdout cannot contain identical records. Perplexity is computed over complete held-out conversations and is only a coarse gate. Also measure exact/semantic task accuracy, schema validity, transcription WER, field accuracy and latency on representative workload data.

Use the [official llama.cpp tools](https://github.com/ggml-org/llama.cpp) from a tested revision to export a **validated** text checkpoint:

```bash
python /path/to/llama.cpp/convert_hf_to_gguf.py artifacts/custom --outfile artifacts/custom-f16.gguf --outtype f16
/path/to/llama.cpp/build/bin/llama-quantize artifacts/custom-f16.gguf models/custom-q4_k_m.gguf Q4_K_M
```

Update `profiles/text.json` to point at the custom GGUF. Re-evaluate the quantized model: post-quantization quality and resource behavior can differ from the float checkpoint. The repository does not trim multilingual token IDs or subtract task vectors automatically; those operations need model-specific tokenizer recovery and stronger quality gates.

For ASR weight tuning or natural TTS voice adaptation, the serving interfaces can load compatible custom checkpoints/profiles, but this repository does not implement an untested generic trainer across acoustic and speech synthesis architectures. Additional speech datasets and architecture-specific training are required. English domain vocabulary and pronunciation customization work now. Image/video hooks deliberately raise `FeatureDeferred`; implement them later in separate workers after deciding the hardware budget and model license.
