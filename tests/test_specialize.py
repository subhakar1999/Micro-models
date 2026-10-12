"""Offline utilities tested on random tiny weights; these tests do not establish domain quality."""
import argparse
import json

import pytest

from scripts import specialize

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("peft")
pytest.importorskip("datasets")

@pytest.fixture
def checkpoint(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM

    words = ["[UNK]", "[PAD]", "[EOS]", "user", "assistant", "invoice", "total", "25", "17", "number", "100", "200"]
    core = Tokenizer(WordLevel({word: i for i, word in enumerate(words)}, unk_token="[UNK]"))
    core.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=core, unk_token="[UNK]", pad_token="[PAD]", eos_token="[EOS]")
    tokenizer.chat_template = ("{% for m in messages %}{{m['role']}} {{m['content']}} [EOS] "
                               "{% endfor %}{% if add_generation_prompt %}assistant {% endif %}")
    torch.manual_seed(42)
    model = Qwen2ForCausalLM(Qwen2Config(vocab_size=len(words), hidden_size=32, intermediate_size=64,
                           num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
                           max_position_embeddings=128, tie_word_embeddings=True))
    path = tmp_path / "tiny"
    model.save_pretrained(path)
    tokenizer.save_pretrained(path)
    training = [{"messages": [{"role": "user", "content": "invoice total"},
                              {"role": "assistant", "content": "25"}]}]
    holdout = [{"messages": [{"role": "user", "content": "invoice number"},
                             {"role": "assistant", "content": "200"}]}]
    train_path, holdout_path = tmp_path / "train.jsonl", tmp_path / "holdout.jsonl"
    train_path.write_text(json.dumps(training[0]))
    holdout_path.write_text(json.dumps(holdout[0]))
    return path, model, tokenizer, training, train_path, holdout_path


def test_calibration_and_pruned_checkpoint_reload(checkpoint, tmp_path, monkeypatch):
    path, model, tokenizer, rows, training, holdout = checkpoint
    scores = specialize.calibrate(model, tokenizer, rows, 64)
    assert len(scores) == 4
    assert all(0 <= score <= 2 for score in scores)
    assert all(not layer._forward_hooks for layer in model.model.layers)
    score_path = tmp_path / "scores.json"
    score_path.write_text(json.dumps({"model": str(path), "block_influence": scores}))
    output = tmp_path / "pruned"
    monkeypatch.setattr("sys.argv", ["specialize", "prune", "--model", str(path), "--data", str(training),
                        "--holdout", str(holdout), "--scores", str(score_path), "--fraction", "0.25",
                        "--max-ppl-ratio", "100", "--output", str(output)])
    specialize.main()
    candidate, _ = specialize.load(output)
    assert len(candidate.model.layers) == 3
    assert [layer.self_attn.layer_idx for layer in candidate.model.layers] == [0, 1, 2]
    # Cached generation catches bugs which use_cache=False perplexity alone would miss.
    result = candidate.generate(input_ids=torch.tensor([[3, 5, 6]]), max_new_tokens=2,
                                pad_token_id=1, eos_token_id=2)
    assert result.shape[1] > 3


def test_failed_pruning_gate_does_not_export_weights(checkpoint, tmp_path, monkeypatch):
    path, _model, _tokenizer, _rows, training, holdout = checkpoint
    score_path = tmp_path / "scores.json"
    score_path.write_text(json.dumps({"model": str(path), "block_influence": [0.1] * 4}))
    output = tmp_path / "rejected"
    monkeypatch.setattr("sys.argv", ["specialize", "prune", "--model", str(path), "--data", str(training),
                        "--holdout", str(holdout), "--scores", str(score_path), "--fraction", "0.25",
                        "--max-ppl-ratio", "0.0001", "--output", str(output)])
    with pytest.raises(SystemExit, match="Quality gate failed"):
        specialize.main()
    assert not (output / "model.safetensors").exists()
    assert not json.loads((output / "report.json").read_text())["gate_passed"]


def test_lora_training_and_merged_checkpoint(checkpoint, tmp_path):
    pytest.importorskip("accelerate")
    _, model, tokenizer, rows, _, _ = checkpoint
    args = argparse.Namespace(rank=2, epochs=1, max_length=64, output=tmp_path / "trained")
    merged = specialize.train(model, tokenizer, rows, args)
    assert not any("lora" in name for name, _ in merged.named_parameters())
    restored, restored_tokenizer = specialize.load(args.output)
    assert specialize.perplexity(restored, restored_tokenizer, rows, 64) > 0
