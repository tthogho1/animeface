import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from animeface.config import Settings
from animeface.main import create_app

JOB = "0b9c2c4e-1111-4222-8333-444455556666"
OTHER = "0b9c2c4e-9999-4222-8333-444455556666"
RESULT_PNG = b"\x89PNG-result"


def face_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(buf, format="PNG")
    return buf.getvalue()


class FakeComfy:
    def __init__(self):
        self.history: dict = {}
        self.queue = {"queue_running": [], "queue_pending": []}
        self.prompts: list[dict] = []
        self.reject_prompt = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/upload/image":
            return httpx.Response(200, json={"name": "uploaded.png", "subfolder": "", "type": "input"})
        if path == "/prompt":
            if self.reject_prompt:
                return httpx.Response(400, json={"error": "invalid prompt"})
            self.prompts.append(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": JOB, "number": 1, "node_errors": {}})
        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={pid: self.history[pid]} if pid in self.history else {})
        if path == "/queue":
            return httpx.Response(200, json=self.queue)
        if path == "/view":
            assert request.url.params["filename"] == "animeface_00001_.png"
            return httpx.Response(200, content=RESULT_PNG, headers={"content-type": "image/png"})
        return httpx.Response(404)


@pytest.fixture
def comfy():
    return FakeComfy()


@pytest.fixture
def client(comfy):
    http = httpx.AsyncClient(transport=httpx.MockTransport(comfy.handler), base_url="http://comfy")
    with TestClient(create_app(Settings(), http_client=http)) as c:
        yield c


def done_entry():
    return {
        "outputs": {"save": {"images": [{"filename": "animeface_00001_.png", "subfolder": "", "type": "output"}]}},
        "status": {"status_str": "success", "completed": True, "messages": []},
    }


def test_convert_queues_workflow_with_uploaded_face(client, comfy):
    r = client.post(
        "/api/convert",
        files={"image": ("me.png", face_png(), "image/png")},
        data={"prompt": "1boy", "ip_weight": "0.9", "seed": "7"},
    )
    assert r.status_code == 200
    assert r.json() == {"job_id": JOB, "seed": 7}
    wf = comfy.prompts[0]
    assert wf["face"]["inputs"]["image"] == "uploaded.png"
    assert wf["apply_id"]["inputs"]["ip_weight"] == 0.9


def test_convert_rejects_non_image(client):
    r = client.post("/api/convert", files={"image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_convert_rejects_oversized_upload(comfy):
    http = httpx.AsyncClient(transport=httpx.MockTransport(comfy.handler), base_url="http://comfy")
    with TestClient(create_app(Settings(max_upload_bytes=100), http_client=http)) as c:
        r = c.post("/api/convert", files={"image": ("me.png", face_png(), "image/png")})
    assert r.status_code == 413


def test_convert_reports_rejected_workflow(client, comfy):
    comfy.reject_prompt = True
    r = client.post("/api/convert", files={"image": ("me.png", face_png(), "image/png")})
    assert r.status_code == 502


def test_job_status_queued_running_done(client, comfy):
    comfy.queue = {"queue_running": [[1, OTHER]], "queue_pending": [[2, JOB]]}
    assert client.get(f"/api/jobs/{JOB}").json() == {"status": "queued", "position": 1}

    comfy.queue = {"queue_running": [[2, JOB]], "queue_pending": []}
    assert client.get(f"/api/jobs/{JOB}").json() == {"status": "running"}

    comfy.history[JOB] = done_entry()
    assert client.get(f"/api/jobs/{JOB}").json() == {"status": "done", "image_url": f"/api/jobs/{JOB}/image"}

    img = client.get(f"/api/jobs/{JOB}/image")
    assert img.status_code == 200
    assert img.content == RESULT_PNG


def test_job_status_surfaces_execution_error(client, comfy):
    comfy.history[JOB] = {
        "outputs": {},
        "status": {
            "status_str": "error",
            "completed": False,
            "messages": [["execution_error", {"node_type": "ApplyInstantIDAdvanced", "exception_message": "No face detected\n"}]],
        },
    }
    assert client.get(f"/api/jobs/{JOB}").json() == {
        "status": "error",
        "error": "ApplyInstantIDAdvanced: No face detected",
    }


def test_unknown_and_malformed_job_ids_are_404(client):
    assert client.get(f"/api/jobs/{JOB}").status_code == 404
    assert client.get("/api/jobs/..%2Fsecret").status_code == 404
    assert client.get("/api/jobs/not-a-uuid/image").status_code == 404


def test_index_and_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "AnimeFace" in client.get("/").text
