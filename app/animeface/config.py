import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    comfyui_url: str = "http://comfyui:8188"
    checkpoint: str = "animagine-xl-3.1.safetensors"
    instantid_model: str = "ip-adapter_instant_id_sdxl.bin"
    controlnet_model: str = "control_instant_id_sdxl.safetensors"
    # Empty string disables upscaling.
    upscale_model: str = "RealESRGAN_x4plus_anime_6B.pth"
    upscale_model_scale: float = 4.0
    upscale_factor: float = 1.5
    max_upload_bytes: int = 10 * 1024 * 1024
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        return cls(
            comfyui_url=os.getenv("COMFYUI_URL", d.comfyui_url),
            checkpoint=os.getenv("CHECKPOINT", d.checkpoint),
            instantid_model=os.getenv("INSTANTID_MODEL", d.instantid_model),
            controlnet_model=os.getenv("CONTROLNET_MODEL", d.controlnet_model),
            upscale_model=os.getenv("UPSCALE_MODEL", d.upscale_model),
            upscale_model_scale=float(os.getenv("UPSCALE_MODEL_SCALE", d.upscale_model_scale)),
            upscale_factor=float(os.getenv("UPSCALE_FACTOR", d.upscale_factor)),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", d.max_upload_bytes)),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", d.request_timeout)),
        )
