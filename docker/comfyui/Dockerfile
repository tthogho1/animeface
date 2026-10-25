# ComfyUI + ComfyUI_InstantID on CUDA 12.4. Models are NOT baked in; they are
# mounted from EFS at /workspace/ComfyUI/models.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG COMFYUI_REF=master
ARG INSTANTID_REF=main
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Python 3.10 (Ubuntu 22.04 default) for the widest custom-node compatibility.
# build-essential/python3-dev are needed to compile insightface.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-dev build-essential git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /workspace
RUN git clone https://github.com/comfyanonymous/ComfyUI.git \
    && git -C ComfyUI checkout ${COMFYUI_REF}

WORKDIR /workspace/ComfyUI
RUN pip install --upgrade pip setuptools wheel \
    && pip install torch torchvision torchaudio --index-url ${TORCH_INDEX_URL} \
    && pip install -r requirements.txt

# The node's requirements pull both onnxruntime and onnxruntime-gpu; the CPU
# package shadows the GPU one, so remove it and reinstall the GPU build.
RUN git clone https://github.com/cubiq/ComfyUI_InstantID.git custom_nodes/ComfyUI_InstantID \
    && git -C custom_nodes/ComfyUI_InstantID checkout ${INSTANTID_REF} \
    && pip install -r custom_nodes/ComfyUI_InstantID/requirements.txt \
    && pip install insightface==0.7.3 \
    && pip uninstall -y onnxruntime \
    && pip install --force-reinstall --no-deps onnxruntime-gpu

EXPOSE 8188
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
