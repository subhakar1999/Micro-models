from fastapi.testclient import TestClient

import run_ui
from micro_models.api import create_app


def test_ui_document_question_flow(tmp_path, monkeypatch):
    class Backend:
        engine = None

        def document(self, path):
            return {"text": path.read_text(), "fields": {}, "pages": []}

        def text(self, prompt, context, max_tokens, schema):
            return {"text": "30 days", "sources": [item["source"] for item in context]}

    def worker(settings):
        settings = settings.model_copy(update={"data_dir": tmp_path / settings.task})
        return create_app(settings, Backend())

    monkeypatch.setattr(run_ui, "create_app", worker)
    client = TestClient(run_ui.create_ui())
    assert client.get("/").status_code == 200
    document = client.post("/services/document/v1/document",
                           files={"file": ("invoice.pdf", b"Invoice payment due in 30 days")})
    assert document.status_code == 200
    assert client.post("/services/text/v1/memory", json={
        "tenant": "doc-test", "source": "invoice.pdf", "text": document.json()["text"],
    }).status_code == 200
    answer = client.post("/services/text/v1/text", json={"tenant": "doc-test", "prompt": "payment"})
    assert answer.status_code == 200
    assert answer.json()["sources"] == ["invoice.pdf"]
    assert client.post("/services/text/v1/text", json={
        "tenant": "another-document", "prompt": "payment",
    }).json()["sources"] == []
