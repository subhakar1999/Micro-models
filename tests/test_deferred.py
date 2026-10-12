from fastapi.testclient import TestClient

from micro_models.api import create_app
from micro_models.config import Settings


def test_image_and_video_are_explicit_placeholders(tmp_path):
    for task in ("image", "video"):
        client = TestClient(create_app(Settings(task=task, data_dir=tmp_path / task)))
        assert client.post(f"/v1/{task}", json={"prompt": "clouds"}).status_code == 501
        status = client.get("/health").json()
        assert status["implemented"] is False
        assert status["model_loaded"] is False
