"""Inspect, calibrate, prune and LoRA-tune Qwen2/Llama-family text checkpoints.

Training and surgery are offline operations, separate from the serving image.
JSONL examples contain {"messages": [{"role": "user", "content": "..."}, ...]}.
"""
import argparse
import json
from pathlib import Path


def records(path):
    result = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not row.get("messages") or row["messages"][-1]["role"] != "assistant":
                raise ValueError("Each example must end with an assistant answer")
            result.append(row)
    if not result:
        raise ValueError("Dataset is empty")
    return result


def load(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32,
                                               trust_remote_code=False).eval()
    if not hasattr(model, "model") or not hasattr(model.model, "layers"):
        raise ValueError("Only Qwen2/Llama-style decoder layers are supported")
    return model, tokenizer


def encoded(tokenizer, row, maximum):
    return tokenizer(tokenizer.apply_chat_template(row["messages"], tokenize=False),
                     return_tensors="pt", truncation=True, max_length=maximum)


def calibrate(model, tokenizer, rows, maximum):
    import torch
    count = len(model.model.layers)
    totals, positions = [0.0] * count, [0] * count
    handles = []
    for index, layer in enumerate(model.model.layers):
        def hook(module, inputs, output, i=index):
            before = inputs[0].float()
            after = (output[0] if isinstance(output, tuple) else output).float()
            scores = 1 - torch.nn.functional.cosine_similarity(before, after, dim=-1)
            totals[i] += scores.sum().item()
            positions[i] += scores.numel()
        handles.append(layer.register_forward_hook(hook))
    try:
        with torch.inference_mode():
            for row in rows:
                model(**encoded(tokenizer, row, maximum), use_cache=False)
    finally:
        for handle in handles:
            handle.remove()
    return [total / max(1, n) for total, n in zip(totals, positions)]


def perplexity(model, tokenizer, rows, maximum):
    import math

    import torch
    total, count = 0.0, 0
    with torch.inference_mode():
        for row in rows:
            data = encoded(tokenizer, row, maximum)
            n = data["input_ids"].numel() - 1
            if n > 0:
                loss = model(**data, labels=data["input_ids"], use_cache=False).loss.item()
                total += loss * n
                count += n
    if not count:
        raise ValueError("Not enough tokens to evaluate")
    return math.exp(min(50, total / count))


def train(model, tokenizer, rows, args):
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import Trainer, TrainingArguments
    model = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", r=args.rank, lora_alpha=2 * args.rank,
                                           lora_dropout=0.05,
                                           target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
    tokenizer.pad_token = tokenizer.eos_token
    items = []
    for row in rows:
        full = tokenizer.apply_chat_template(row["messages"], tokenize=False)
        prefix = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
        ids = tokenizer(full, truncation=True, max_length=args.max_length, add_special_tokens=False)["input_ids"]
        prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
        if ids[:len(prefix_ids)] != prefix_ids:
            # A mismatched boundary must not accidentally train on prompt tokens.
            raise ValueError("Chat template prefix is incompatible with assistant-only training")
        if len(ids) <= len(prefix_ids):
            continue
        labels = [-100] * len(prefix_ids) + ids[len(prefix_ids):]
        items.append({"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels})
    if not items:
        raise ValueError("No assistant tokens remain after truncation; increase --max-length")

    def collate(batch):
        length = max(len(item["input_ids"]) for item in batch)
        return {key: torch.tensor([item[key] + [pad] * (length - len(item[key])) for item in batch])
                for key, pad in [("input_ids", tokenizer.pad_token_id), ("attention_mask", 0), ("labels", -100)]}

    trainer = Trainer(model=model, args=TrainingArguments(output_dir=str(args.output / "checkpoints"),
                      num_train_epochs=args.epochs, per_device_train_batch_size=1,
                      gradient_accumulation_steps=8, learning_rate=2e-4, report_to="none",
                      save_strategy="no", logging_steps=5, seed=42, use_cpu=not torch.cuda.is_available()),
                      train_dataset=Dataset.from_list(items), data_collator=collate)
    trainer.train()
    merged = model.merge_and_unload().eval()
    merged.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "calibrate", "prune", "train", "evaluate"])
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/text-custom"))
    parser.add_argument("--fraction", type=float, default=0.1)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-ppl-ratio", type=float, default=1.15)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    import torch
    torch.set_num_threads(2)
    model, tokenizer = load(args.model)
    if args.action == "inspect":
        embeddings = model.get_input_embeddings()
        head = model.get_output_embeddings()
        tied = embeddings.weight.data_ptr() == head.weight.data_ptr()
        report = {"model": args.model, "parameters": sum(p.numel() for p in model.parameters()),
                  "layers": len(model.model.layers), "vocabulary": embeddings.num_embeddings,
                  "embedding_parameters": embeddings.weight.numel(), "tied_output_head": tied,
                  "hidden_size": model.config.hidden_size}
    else:
        if not args.data:
            parser.error("--data is required")
        rows = records(args.data)
        if args.action == "calibrate":
            report = {"model": args.model, "examples": len(rows), "max_length": args.max_length,
                      "block_influence": calibrate(model, tokenizer, rows, args.max_length)}
        elif args.action == "evaluate":
            report = {"model": args.model, "perplexity": perplexity(model, tokenizer, rows, args.max_length)}
        else:
            if not args.holdout or args.holdout.resolve() == args.data.resolve():
                parser.error("A separate --holdout JSONL file is required")
            validation = records(args.holdout)
            # Prevent identical records from leaking from training/calibration into holdout.
            if {json.dumps(r, sort_keys=True) for r in rows} & {json.dumps(r, sort_keys=True) for r in validation}:
                raise ValueError("Training/calibration examples overlap the holdout")
            baseline = perplexity(model, tokenizer, validation, args.max_length)
            removed = []
            if args.action == "prune":
                if not 0 < args.fraction <= 0.25:
                    parser.error("--fraction must be in (0, 0.25]")
                if not args.scores:
                    parser.error("--scores must reference a calibration report.json")
                scores = json.loads(args.scores.read_text(encoding="utf-8"))
                layers = model.model.layers
                if scores["model"] != args.model or len(scores["block_influence"]) != len(layers):
                    raise ValueError("Calibration scores do not match the model")
                # Preserve first/last layer; begin with a conservative calibration-selected cut.
                count = max(1, int(len(layers) * args.fraction))
                removed = sorted(sorted(range(1, len(layers) - 1),
                                        key=lambda i: scores["block_influence"][i])[:count])
                model.model.layers = torch.nn.ModuleList([layer for i, layer in enumerate(layers) if i not in removed])
                model.config.num_hidden_layers = len(model.model.layers)
                if isinstance(getattr(model.config, "layer_types", None), list):
                    model.config.layer_types = [kind for i, kind in enumerate(model.config.layer_types)
                                                if i not in removed]
                for i, layer in enumerate(model.model.layers):
                    layer.self_attn.layer_idx = i
            else:
                model = train(model, tokenizer, rows, args)
            candidate = perplexity(model, tokenizer, validation, args.max_length)
            passed = candidate / baseline <= args.max_ppl_ratio
            report = {"model": args.model, "baseline_perplexity": baseline, "candidate_perplexity": candidate,
                      "ratio": candidate / baseline, "gate_passed": passed, "removed_layers": removed,
                      "quality_note": "Perplexity is only one gate; also evaluate task accuracy before deployment."}
            if args.action == "prune":
                if not passed:
                    args.output.mkdir(parents=True, exist_ok=True)
                    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    raise SystemExit("Quality gate failed; pruned weights were not saved")
                model.save_pretrained(args.output)
                tokenizer.save_pretrained(args.output)
            elif not passed:
                report["quality_note"] += " Training candidate failed: saved for inspection only."
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
