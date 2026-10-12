# Research audit

The supplied text is an architectural survey assembled from multiple sources, with missing equations and some damaged character encoding. It is not enough to reproduce a trained multimodal model: datasets, exact checkpoints, calibration corpora, training runs and evaluation protocols are absent. The implementation uses public inference interfaces and parameter inspection, rather than implying recovery of proprietary weights.

| Claim in supplied text | Finding and implementation consequence |
| --- | --- |
| Qwen 0.5B embeddings/output consume over half its weights | The publisher reports 0.49B total, 0.36B non-embedding and **tied** embeddings. The input/output matrices share storage, so they must not be double-counted. Vocabulary pruning does not automatically halve this model. |
| Qwen variants share 128K context | The selected 0.5B model card specifies 32,768 tokens. Serving deliberately caps context at 2,048 to reduce KV memory. |
| Layer cuts preserve accuracy after a short recovery | ShortGPT supports calibration-based redundancy analysis; equal dimensions establish shape compatibility, not equivalent behavior. Cuts must be evaluated on separate held-out data. No unvalidated cut is enabled by default. |
| Vocabulary shearing preserves universal runtime compatibility | Removing tokenizer merges/IDs can break byte coverage, special tokens, templates and GGUF conversion. There is no blind tokenizer surgery in the serving path. |
| A 160 MB Kokoro weight estimate is total serving RAM | The 82M parameter count is real; Torch, G2P, voices and intermediate tensors add memory. eSpeak NG is the low-resource default, with Kokoro optional. |
| INT8 Whisper occupies only tens of MB in service | Weight storage is not RSS. CTranslate2, decoding, VAD and activations also need memory. The tiny.en service is measured locally, not assigned a guaranteed latency. |
| OCR micro-models are suitable for the smallest VM | Generative OCR adds a decoder and model runtime. This implementation tries native PDF text first, then classical English OCR, accepting weaker table/math fidelity. |
| LTX-2 is a 2B video model | The publisher's LTX-2 card lists **19B** parameters. LTX-Video versions also differ substantially. Both image and video generation were deferred by the user. |
| mmap swaps multi-GB CPU/GPU models in tens of ms | mmap maps virtual addresses; it does not guarantee residency, zero-copy GPU access or fast cold page faults. Loading, disk I/O and PCIe transfer must be measured separately. |
| Semantic routing always takes under 5 ms | Encoder choice, hardware and queueing affect latency. Explicit task routes have no encoder cost and are sufficient for this deployment. |
| Task-vector subtraction reliably removes unwanted behaviors | Weight arithmetic requires compatible checkpoints and controlled evaluation; it does not guarantee isolation or capability preservation. Task-scoped prompts and supervised adaptation are used instead. |

Primary sources checked for this implementation:

- [Qwen2.5-0.5B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct): parameter sharing, context and architecture.
- [Publisher's GGUF release](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF): downloadable quantized baseline, Apache 2.0.
- [faster-whisper repository](https://github.com/SYSTRAN/faster-whisper): CTranslate2 INT8 serving and CPU benchmark conditions. Published small-model benchmarks are not treated as tiny.en results on Google Cloud.
- [Kokoro repository](https://github.com/hexgrad/kokoro): 82M model, KPipeline usage, voice and phonemization requirements.
- [Tesseract repository](https://github.com/tesseract-ocr/tesseract): OCR engine and trained data requirements.
- [eSpeak NG repository](https://github.com/espeak-ng/espeak-ng): compact rule-based synthesis. Its GPL license differs from the neural model licenses; preserve upstream notices when distributing its executable/container.
- [ShortGPT paper](https://arxiv.org/abs/2403.03853): block influence and layer redundancy.
- [llama.cpp repository](https://github.com/ggml-org/llama.cpp): quantized inference, GGUF tooling and CPU execution.
- [LTX-2 publisher model card](https://huggingface.co/Lightricks/LTX-2): 19B model scale, relevant only to a future extension.

The deployment recommendation is CPU quantization + isolated tasks + bounded inputs first. Training, pruning or distillation adds complexity and must produce demonstrable task-quality and resource improvements before replacing the baseline.
