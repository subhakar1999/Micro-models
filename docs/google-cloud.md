# Google Cloud within a free-tier budget

The intended use is English, Python and low-volume CPU inference. A zero-dollar outcome depends on **total account usage**, not only this service. No cloud deployment has been performed.

Google's [free-tier documentation](https://docs.cloud.google.com/free/docs/free-cloud-features) lists request-billed Cloud Run allowances of 180,000 vCPU-seconds, 360,000 GB-seconds and two million requests monthly. Allowances are shared across eligible usage. Cloud Run outbound data has a separate allowance. Compute Engine's eligible e2-micro regions are us-central1, us-west1 and us-east1, with 30 GB-months standard persistent disk. GPUs/TPUs are excluded. The $300/90-day trial is separate from the ongoing free tier.

Prefer a single **Cloud Run** task initially: one instance maximum, zero minimum, concurrency one, request-based CPU billing, no GPU. The deployment script accepts only text, ASR, TTS and document workers. Memory settings are starting estimates; confirm cold-load and peak memory on the deployed container before relying on them. A 1 GiB e2-micro has little headroom for simultaneous models, so an always-on four-model stack is not the target.

## Build locally

Docker must be running. Choose one task and build outside Google Cloud to avoid consuming Cloud Build allowance. Build examples:

```bash
docker build --build-arg EXTRA=text -t micro-text .
docker build --build-arg EXTRA=asr -t micro-asr .
docker build --build-arg EXTRA=ocr -t micro-document .
docker build --build-arg EXTRA=lite -t micro-tts .
```

The text build embeds the publisher's Q4_K_M GGUF. ASR pre-fetches tiny.en. The other builds require no model download at runtime. Native Tesseract and eSpeak executables are included. Build one selected image at a time; the combined storage of all four images can exceed the registry allowance. This Dockerfile deliberately excludes Torch/Kokoro from the free-tier images.

Test before pushing:

```bash
docker run --rm -p 8000:8080 --memory=1g --cpus=1 \
  -e MICRO_TASK=text -e MICRO_TEXT_BACKEND=gguf \
  -e MICRO_PROFILE_PATH=/app/profiles/text.json micro-text
```

For the other tasks replace the image, task and profile. Omit `MICRO_TEXT_BACKEND` outside text. Use `scripts/benchmark.py` against the running container and `docker stats` for memory including native processes. Try 512 MiB for document/TTS only after confirming peak behavior.

## Push and deploy an existing image

Use an image registry you already have available, then run:

```bash
bash deploy/cloud-run.sh text IMAGE_URI YOUR_PROJECT_ID
```

The script deploys a private service in us-central1 with request-based billing, min instances zero, max instances one and concurrency one. It does not enable APIs, create registries or upgrade billing accounts. Google Cloud must already have the needed APIs enabled and access to the image. Use your authenticated Cloud Run endpoint with:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2 plus 2?","max_tokens":16}' \
  https://YOUR_SERVICE_URL/v1/text
```

Cloud Run IAM verifies the Google token. `MICRO_API_KEY` is left unset in this recipe to avoid a second, incompatible Bearer token requirement. Keep the service private.

## Keep the full deployment within allowances

For a rough request budget, sum `vCPUs × active seconds` and `allocated RAM × active seconds` across **all** services and revisions. Cold starts and repeated loads count too. A one-vCPU, one-GiB service has at most 50 hours within the 180,000 vCPU-second allowance if the whole allowance is otherwise unused; this is an allowance calculation, not a throughput guarantee. Do not budget by request count alone.

[Artifact Registry](https://docs.cloud.google.com/free/docs/free-cloud-features) includes only 0.5 GB storage/month in its free allowance. A text image with baked-in weights or several retained revisions may exceed that. Local builds avoid Cloud Build time but do not make image storage free. Inspect compressed image storage before pushing; delete unneeded versions or choose a registry with suitable free storage. Builds, logs, networking and persistence have their own limits. Maximum instances limits concurrency, not total monthly charges. Google Cloud budget alerts also do not stop spending automatically.

Cloud Run's writable filesystem is temporary and consumes memory. Retrieval uploaded through `/v1/memory` disappears with the instance. For durable knowledge, use a persistent VM directory or add a deliberately chosen storage integration; the repository does not claim durable multi-instance memory.

For strict zero-cost operation, start locally, measure actual request demand and image size, and deploy only a task that fits all applicable allowances. If any allowance is exhausted, stop that service rather than silently switching to paid inference. Current prices/eligibility should be checked in [Cloud Run pricing](https://cloud.google.com/run/pricing) and the account's billing reports before deployment.
