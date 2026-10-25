# AnimeFace

Turn a face photo into an anime portrait that keeps the person's identity.
**ComfyUI + SDXL (Animagine XL 3.1) + InstantID** on a self-managed k3s cluster on EC2,
built with **Terraform** (AWS) and **Ansible** (cluster + app).

```
Browser ──▶ Traefik Ingress (control-plane public IP :80)
              │
              ▼
        animeface-app  (FastAPI + static UI, CPU)          ns: animeface
              │  /upload/image, /prompt, /history, /view
              ▼
        comfyui  (ComfyUI + ComfyUI_InstantID, 1x GPU, runtimeClass nvidia)
              │
              ├── PVC anime-models-efs  ─▶ EFS access point /models
              └── PVC anime-outputs-efs ─▶ EFS access point /outputs
```

| Layer | What | Where |
|---|---|---|
| AWS infra | VPC, public subnet, SGs, EC2 (k3s server `t3.medium` + GPU workers `g5.xlarge`), EFS (elastic throughput, 2 access points), ECR, IAM instance profile | `terraform/` |
| Cluster | k3s, NVIDIA device plugin, EFS CSI driver, ECR pull-secret refresh timer | `ansible/roles/{common,k3s_server,k3s_agent,cluster_addons,ecr_auth}` |
| Models | k8s Job that downloads checkpoint, InstantID, ControlNet, antelopev2 and upscaler onto EFS | `ansible/roles/animeface/templates/model-download.yaml.j2` |
| ComfyUI image | CUDA 12.4 + PyTorch + ComfyUI + ComfyUI_InstantID + insightface + onnxruntime-gpu (models not baked in) | `docker/comfyui/Dockerfile` |
| Web app | Upload → InstantID workflow → poll → result | `app/` |

GPU nodes use the **AWS Deep Learning Base OSS Nvidia Driver AMI (Ubuntu 22.04)**. It ships with the
NVIDIA driver and container toolkit, so k3s registers the `nvidia` runtime automatically and
no GPU Operator is needed.

## Prerequisites

- AWS credentials with admin-ish rights; **G-instance vCPU quota ≥ 4** in your region
  (Service Quotas → "Running On-Demand G and VT instances").
- `terraform >= 1.5`, `ansible-core >= 2.15`, `aws` CLI v2, Docker with `buildx`.
- An SSH key pair (default `~/.ssh/id_ed25519{,.pub}`).

## Deploy

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# edit allowed_cidrs -> your IP (/32)

make init
make infra     # ~3 min. Writes ansible/inventory/hosts.ini + group_vars/all/terraform.yml
make images    # builds linux/amd64 images and pushes to ECR. ComfyUI image is large; on Apple Silicon expect 20-40 min
make cluster   # k3s + add-ons + model download (~10GB) + deploy. First run 20-40 min
```

Open the URL printed at the end (also `terraform -chdir=terraform output app_url`).

Day-2:

```bash
make images && make deploy   # ship app/ComfyUI changes
make ui                      # ComfyUI editor at http://localhost:8188 (not exposed publicly)
make logs                    # ComfyUI logs
export KUBECONFIG=$PWD/kubeconfig && kubectl get pods -A
```

Optional: `export HF_TOKEN=hf_...` before `make cluster` if Hugging Face rate-limits or gates a download.

## Tuning

These are app defaults. The UI exposes the first two.

| Parameter | Default | Notes |
|---|---|---|
| InstantID weight (`ip_weight`) | 0.8 | ↑ more like the photo, ↓ more anime |
| ControlNet strength (`cn_strength`) | 0.7 | ↓ if the face is distorted |
| steps / CFG | 30 / 5.0 | `app/animeface/workflow.py` |
| sampler | dpmpp_2m karras | |
| size | 1024×1024, then 1.5× upscale with RealESRGAN anime 6B | `UPSCALE_FACTOR`, `UPSCALE_MODEL=""` disables |

Swap models by editing `models:` / `*_file` in `ansible/inventory/group_vars/all/main.yml` and running `make deploy`.

## Costs & shutdown

`g5.xlarge` costs roughly $1.4/h in ap-northeast-1, and EFS is billed per GB stored (~10GB of models).
- Pause GPU spend: set `gpu_worker_count = 0` and run `make infra`. Set it back to `1`, then `make infra && make cluster` (models stay on EFS).
- Remove everything: `make destroy`.

## Security notes

- SG allows 22/6443/80/443 only from `allowed_cidrs`. The app has **no authentication**, so add
  auth or TLS before exposing it more widely.
- The ComfyUI API/editor is ClusterIP-only. Use `make ui` (kubectl port-forward).
- Uploaded faces are re-encoded (EXIF stripped) and stored in the pod's ephemeral input dir.
  Generated images persist on EFS `/outputs`.

## Troubleshooting

| Symptom | Check |
|---|---|
| `make infra` fails with `InsufficientInstanceCapacity` / unsupported | set `availability_zone` to another AZ |
| comfyui pod Pending | `kubectl describe node -l nvidia.com/gpu.present=true` should show `nvidia.com/gpu: 1`; check `nvidia-device-plugin` pods |
| `ImagePullBackOff` | `sudo systemctl start animeface-ecr-refresh` on the server; confirm `make images` pushed the tag in `.image-tag` |
| Job "no face detected" | use a front-facing, well-lit photo with one face |
| antelopev2 download 404 | the community mirror moved; update the URLs in `group_vars/all/main.yml` |
| `InstantIDFaceAnalysis` falls back to CPU | `kubectl exec deploy/comfyui -- python -c "import onnxruntime as o; print(o.get_available_providers())"` must list `CUDAExecutionProvider` |

## Development

```bash
cd app && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest      # ComfyUI is mocked via httpx.MockTransport
COMFYUI_URL=http://localhost:8188 .venv/bin/uvicorn animeface.main:app --reload   # with `make ui` running
```
