"""Thin async client for the ComfyUI HTTP API."""

from dataclasses import dataclass

import httpx


class ComfyError(Exception):
    """ComfyUI rejected a request (e.g. workflow validation failed)."""


class ComfyUnavailable(Exception):
    """ComfyUI could not be reached."""


@dataclass(frozen=True)
class OutputImage:
    filename: str
    subfolder: str
    type: str


class ComfyClient:
    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._http.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            raise ComfyUnavailable(str(e)) from e

    async def upload_image(self, data: bytes, filename: str) -> str:
        r = await self._request(
            "POST",
            "/upload/image",
            files={"image": (filename, data, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        if r.status_code != 200:
            raise ComfyError(f"image upload failed: HTTP {r.status_code} {r.text[:200]}")
        body = r.json()
        sub = body.get("subfolder") or ""
        return f"{sub}/{body['name']}" if sub else body["name"]

    async def queue_prompt(self, workflow: dict, client_id: str) -> str:
        r = await self._request("POST", "/prompt", json={"prompt": workflow, "client_id": client_id})
        if r.status_code != 200:
            raise ComfyError(f"workflow rejected: {r.text[:500]}")
        return r.json()["prompt_id"]

    async def get_history(self, prompt_id: str) -> dict | None:
        r = await self._request("GET", f"/history/{prompt_id}")
        r.raise_for_status()
        return r.json().get(prompt_id)

    async def get_queue(self) -> dict:
        r = await self._request("GET", "/queue")
        r.raise_for_status()
        return r.json()

    async def fetch_image(self, img: OutputImage) -> tuple[bytes, str]:
        r = await self._request(
            "GET",
            "/view",
            params={"filename": img.filename, "subfolder": img.subfolder, "type": img.type},
        )
        if r.status_code != 200:
            raise ComfyError(f"image fetch failed: HTTP {r.status_code}")
        return r.content, r.headers.get("content-type", "image/png")


def output_images(history_entry: dict) -> list[OutputImage]:
    images = []
    for node_output in history_entry.get("outputs", {}).values():
        for img in node_output.get("images", []):
            if img.get("type") == "output":
                images.append(OutputImage(img["filename"], img.get("subfolder", ""), img["type"]))
    return images


def error_message(history_entry: dict) -> str | None:
    status = history_entry.get("status", {})
    if status.get("status_str") != "error":
        return None
    for event, data in status.get("messages", []):
        if event == "execution_error":
            return f"{data.get('node_type', 'node')}: {data.get('exception_message', '').strip()}"
    return "generation failed"
