from dataclasses import replace

from animeface.config import Settings
from animeface.workflow import BASE_POSITIVE, SAVE_NODE, ConvertParams, build_workflow

PARAMS = ConvertParams(face_image="face.png", seed=42, prompt="1girl, red hair", ip_weight=0.75)


def assert_links_resolve(wf: dict) -> None:
    for node_id, node in wf.items():
        for value in node["inputs"].values():
            if isinstance(value, list):
                assert value[0] in wf, f"{node_id} links to missing node {value[0]}"


def test_workflow_wires_instantid_into_sampler():
    wf = build_workflow(PARAMS, Settings())
    assert_links_resolve(wf)

    apply_id = wf["apply_id"]
    assert apply_id["class_type"] == "ApplyInstantIDAdvanced"
    assert apply_id["inputs"]["ip_weight"] == 0.75
    assert apply_id["inputs"]["image"] == ["face", 0]
    assert wf["face"]["inputs"]["image"] == "face.png"

    sampler = wf["sampler"]["inputs"]
    assert sampler["model"] == ["apply_id", 0]
    assert sampler["positive"] == ["apply_id", 1]
    assert sampler["negative"] == ["apply_id", 2]
    assert sampler["seed"] == 42

    assert wf["pos"]["inputs"]["text"] == f"1girl, red hair, {BASE_POSITIVE}"
    assert wf["ckpt"]["inputs"]["ckpt_name"] == "animagine-xl-3.1.safetensors"


def test_upscale_resizes_to_target_factor():
    wf = build_workflow(PARAMS, Settings(upscale_factor=2.0, upscale_model_scale=4.0))
    assert wf["resize"]["inputs"]["scale_by"] == 0.5
    assert wf[SAVE_NODE]["inputs"]["images"] == ["resize", 0]


def test_upscale_disabled_saves_decoded_image():
    wf = build_workflow(replace(PARAMS, prompt=""), Settings(upscale_model=""))
    assert_links_resolve(wf)
    assert "upscale" not in wf
    assert wf[SAVE_NODE]["inputs"]["images"] == ["decode", 0]
    assert wf["pos"]["inputs"]["text"] == BASE_POSITIVE
