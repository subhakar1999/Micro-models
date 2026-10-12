import threading

from fastapi.testclient import TestClient

from micro_models.api import create_app
from micro_models.config import Settings


class FakeBackend:
    engine = None

    def text(self, prompt, context, max_tokens, schema):
        return {"text": "test response", "sources": [c["source"] for c in context]}

    def document(self, path):
        assert path.exists()
        return {"text": path.read_text(), "pages": [], "fields": {}}


def test_auth_grounding_and_tenant_isolation(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, api_key="secret"), FakeBackend()))
    assert client.post("/v1/text", json={"prompt": "invoice"}).status_code == 401
    headers = {"Authorization": "Bearer secret"}
    assert client.post("/v1/memory", headers=headers,
                       json={"tenant": "a", "source": "policy", "text": "invoice due in 30 days"}).status_code == 200
    response = client.post("/v1/text", headers=headers, json={"tenant": "a", "prompt": "invoice"})
    assert response.json()["sources"] == ["policy"]
    assert client.post("/v1/text", headers=headers,
                       json={"tenant": "b", "prompt": "invoice"}).json()["sources"] == []
    assert client.post("/v1/text", headers=headers, json={"prompt": "x", "max_tokens": 4096}).status_code == 422


def test_upload_limits_and_cleanup(tmp_path):
    client = TestClient(create_app(Settings(task="document", data_dir=tmp_path, max_upload_bytes=10), FakeBackend()))
    assert client.post("/v1/document", files={"file": ("a.txt", b"hello")}).json()["text"] == "hello"
    assert not list(tmp_path.iterdir())
    assert client.post("/v1/document", files={"file": ("a.txt", b"x" * 11)}).status_code == 413
    assert not list(tmp_path.iterdir())
    assert client.post("/v1/document", files={"file": ("a.txt", b"")}).status_code == 422
    assert not list(tmp_path.iterdir())


def test_wrong_worker_does_not_accept_upload(tmp_path):
    client = TestClient(create_app(Settings(task="tts", data_dir=tmp_path), FakeBackend()))
    assert client.post("/v1/document", files={"file": ("a.pdf", b"x")}).status_code == 404
    assert not list(tmp_path.iterdir())


def test_parallel_request_rejected_and_lock_released(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class Blocking(FakeBackend):
        def text(self, *args):
            entered.set()
            assert release.wait(5)
            raise ValueError("controlled failure")

    client = TestClient(create_app(Settings(data_dir=tmp_path), Blocking()))
    responses = []
    thread = threading.Thread(target=lambda: responses.append(client.post("/v1/text", json={"prompt": "x"})))
    thread.start()
    assert entered.wait(5)
    try:
        assert client.post("/v1/text", json={"prompt": "y"}).status_code == 429
    finally:
        release.set()
        thread.join(5)
    assert responses[0].status_code == 422
    assert client.post("/v1/text", json={"prompt": "z"}).status_code == 422


def test_render_validation(tmp_path):
    client = TestClient(create_app(Settings(task="video", data_dir=tmp_path), FakeBackend()))
    assert client.post("/v1/video", json={"prompt": "clouds", "frames": 32}).status_code == 422
    assert client.post("/v1/video", json={"prompt": "clouds", "width": 1000}).status_code == 422
    assert client.post("/v1/video", json={"prompt": "clouds", "width": 1024, "height": 1024}).status_code == 422


def test_large_body_rejected_before_parsing(tmp_path):
    client = TestClient(create_app(Settings(task="document", data_dir=tmp_path, max_upload_bytes=10), FakeBackend()))
    response = client.post("/v1/document", content=b"x" * 70_000,
                           headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert response.status_code == 413
    assert not list(tmp_path.iterdir())


def test_chunked_body_rejected(tmp_path):
    client = TestClient(create_app(Settings(task="document", data_dir=tmp_path, max_upload_bytes=10), FakeBackend()))
    def chunks():
        yield b"x" * 35_000
        yield b"x" * 35_000
    response = client.post("/v1/document", content=chunks(),
                           headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert response.status_code == 413
