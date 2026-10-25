import io
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from .comfy import ComfyClient, ComfyError, ComfyUnavailable, error_message, output_images
from .config import Settings
from .workflow import ConvertParams, build_workflow

JOB_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_FACE_SIDE = 1024
STATIC_DIR = Path(__file__).parent / "static"


def prepare_face_image(data: bytes) -> bytes:
    """Decode, apply EXIF rotation, strip metadata, shrink and re-encode as PNG."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise HTTPException(400, "Unsupported or corrupt image") from e
    img.thumbnail((MAX_FACE_SIDE, MAX_FACE_SIDE))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def create_app(settings: Settings | None = None, http_client: httpx.AsyncClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = http_client or httpx.AsyncClient(
            base_url=settings.comfyui_url, timeout=settings.request_timeout
        )
        app.state.comfy = ComfyClient(client)
        try:
            yield
        finally:
            if http_client is None:
                await client.aclose()

    app = FastAPI(title="AnimeFace", lifespan=lifespan)

    def comfy(request: Request) -> ComfyClient:
        return request.app.state.comfy

    def check_job_id(job_id: str) -> None:
        if not JOB_ID_RE.match(job_id):
            raise HTTPException(404, "Unknown job")

    @app.exception_handler(ComfyUnavailable)
    async def comfy_unavailable(_: Request, exc: ComfyUnavailable):
        return Response('{"detail":"Image generator is unavailable"}', 503, media_type="application/json")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.post("/api/convert")
    async def convert(
        request: Request,
        image: UploadFile = File(...),
        prompt: str = Form("", max_length=500),
        negative_prompt: str = Form("", max_length=500),
        ip_weight: float = Form(0.8, ge=0.0, le=1.5),
        cn_strength: float = Form(0.7, ge=0.0, le=1.5),
        seed: int | None = Form(None, ge=0, le=2**32 - 1),
    ):
        data = await image.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"Image larger than {settings.max_upload_bytes // (1024 * 1024)}MB")
        png = await run_in_threadpool(prepare_face_image, data)

        client = comfy(request)
        try:
            face_name = await client.upload_image(png, f"animeface_{uuid.uuid4().hex}.png")
            params = ConvertParams(
                face_image=face_name,
                seed=seed if seed is not None else secrets.randbelow(2**32),
                prompt=prompt,
                negative_prompt=negative_prompt,
                ip_weight=ip_weight,
                cn_strength=cn_strength,
            )
            job_id = await client.queue_prompt(build_workflow(params, settings), client_id="animeface")
        except ComfyError as e:
            raise HTTPException(502, str(e)) from e
        return {"job_id": job_id, "seed": params.seed}

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str, request: Request):
        check_job_id(job_id)
        client = comfy(request)
        entry = await client.get_history(job_id)
        if entry is None:
            queue = await client.get_queue()
            if any(item[1] == job_id for item in queue.get("queue_running", [])):
                return {"status": "running"}
            pending = [item[1] for item in sorted(queue.get("queue_pending", []), key=lambda i: i[0])]
            if job_id in pending:
                return {"status": "queued", "position": pending.index(job_id) + 1}
            raise HTTPException(404, "Unknown job")

        if err := error_message(entry):
            return {"status": "error", "error": err}
        if entry.get("status", {}).get("completed") and output_images(entry):
            return {"status": "done", "image_url": f"/api/jobs/{job_id}/image"}
        return {"status": "running"}

    @app.get("/api/jobs/{job_id}/image")
    async def job_image(job_id: str, request: Request):
        check_job_id(job_id)
        client = comfy(request)
        entry = await client.get_history(job_id)
        images = output_images(entry) if entry else []
        if not images:
            raise HTTPException(404, "Image not ready")
        try:
            content, media_type = await client.fetch_image(images[0])
        except ComfyError as e:
            raise HTTPException(502, str(e)) from e
        return Response(content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
