import json

import httpx
import pytest

from micro_models.backends import Backend, BackendUnavailable
from micro_models.config import Profile, Settings


def test_text_http_contract(monkeypatch):
    def respond(request):
        assert str(request.url) == "http://worker/v1/chat/completions"
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
        assert body["messages"][-1]["content"] == "test"
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(respond)))
    engine = Backend(Settings(text_url="http://worker/v1"), Profile(task="text"))
    assert engine.text("test", [], 20, {"type": "object"})["text"] == "{}"


def test_profile_mismatch(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text('{"task":"asr"}')
    with pytest.raises(ValueError, match="does not match"):
        Settings(task="text", profile_path=path).profile()


def test_missing_gguf_is_explicit(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules, "llama_cpp", SimpleNamespace(Llama=object))
    engine = Backend(Settings(text_backend="gguf"), Profile(task="text", model=str(tmp_path / "absent.gguf")))
    with pytest.raises(BackendUnavailable, match="downloaded GGUF"):
        engine.text("test", [], 20, None)
