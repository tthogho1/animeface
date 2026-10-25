"""Builds the ComfyUI API-format workflow for face -> anime conversion.

Graph:
  Checkpoint (Animagine XL) ─┬─ CLIP text encode (+/-) ─┐
  InstantID model ───────────┤                          │
  InsightFace (antelopev2) ──┼── ApplyInstantIDAdvanced ┴─ KSampler ─ VAE Decode
  InstantID ControlNet ──────┤                                            │
  Face image ────────────────┘                    [Upscale model ─ resize] ─ Save
"""

from dataclasses import dataclass

from .config import Settings

BASE_POSITIVE = (
    "masterpiece, best quality, very aesthetic, absurdres, anime style, clean lineart, "
    "detailed eyes, portrait, upper body, looking at viewer, soft lighting"
)
BASE_NEGATIVE = (
    "worst quality, low quality, blurry, lowres, jpeg artifacts, extra fingers, bad hands, "
    "deformed face, bad anatomy, photorealistic, realistic skin, 3d, photo"
)

SAVE_NODE = "save"


@dataclass(frozen=True)
class ConvertParams:
    face_image: str  # filename in ComfyUI's input directory
    seed: int
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 30
    cfg: float = 5.0
    ip_weight: float = 0.8
    cn_strength: float = 0.7


def build_positive(user_prompt: str) -> str:
    user_prompt = user_prompt.strip().strip(",")
    return f"{user_prompt}, {BASE_POSITIVE}" if user_prompt else BASE_POSITIVE


def build_negative(user_negative: str) -> str:
    user_negative = user_negative.strip().strip(",")
    return f"{user_negative}, {BASE_NEGATIVE}" if user_negative else BASE_NEGATIVE


def build_workflow(p: ConvertParams, s: Settings) -> dict:
    wf: dict[str, dict] = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": s.checkpoint}},
        "instantid": {
            "class_type": "InstantIDModelLoader",
            "inputs": {"instantid_file": s.instantid_model},
        },
        "insightface": {"class_type": "InstantIDFaceAnalysis", "inputs": {"provider": "CUDA"}},
        "controlnet": {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": s.controlnet_model},
        },
        "face": {"class_type": "LoadImage", "inputs": {"image": p.face_image}},
        "pos": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": build_positive(p.prompt), "clip": ["ckpt", 1]},
        },
        "neg": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": build_negative(p.negative_prompt), "clip": ["ckpt", 1]},
        },
        "apply_id": {
            "class_type": "ApplyInstantIDAdvanced",
            "inputs": {
                "instantid": ["instantid", 0],
                "insightface": ["insightface", 0],
                "control_net": ["controlnet", 0],
                "image": ["face", 0],
                "model": ["ckpt", 0],
                "positive": ["pos", 0],
                "negative": ["neg", 0],
                "ip_weight": p.ip_weight,
                "cn_strength": p.cn_strength,
                "start_at": 0.0,
                "end_at": 1.0,
                "noise": 0.0,
                "combine_embeds": "average",
            },
        },
        "latent": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": p.width, "height": p.height, "batch_size": 1},
        },
        "sampler": {
            "class_type": "KSampler",
            "inputs": {
                "seed": p.seed,
                "steps": p.steps,
                "cfg": p.cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["apply_id", 0],
                "positive": ["apply_id", 1],
                "negative": ["apply_id", 2],
                "latent_image": ["latent", 0],
            },
        },
        "decode": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["sampler", 0], "vae": ["ckpt", 2]},
        },
    }

    final_image = ["decode", 0]
    if s.upscale_model and s.upscale_factor > 1.0:
        wf["upscaler"] = {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": s.upscale_model},
        }
        wf["upscale"] = {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["upscaler", 0], "image": final_image},
        }
        # The model upscales by a fixed factor (4x); resize down to the target factor.
        wf["resize"] = {
            "class_type": "ImageScaleBy",
            "inputs": {
                "image": ["upscale", 0],
                "upscale_method": "lanczos",
                "scale_by": s.upscale_factor / s.upscale_model_scale,
            },
        }
        final_image = ["resize", 0]

    wf[SAVE_NODE] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "animeface", "images": final_image},
    }
    return wf
