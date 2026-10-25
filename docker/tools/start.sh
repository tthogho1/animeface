#!/usr/bin/env bash
# Start a shell (or run a command) in the Terraform + Ansible + AWS CLI image.
#   docker/tools/start.sh                 # interactive shell
#   docker/tools/start.sh make infra      # run a single command
#   docker/tools/start.sh --build         # rebuild the image first
set -euo pipefail

IMAGE="${TOOLS_IMAGE:-animeface-tools}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ "${1:-}" == "--build" ]]; then
  shift
  docker build -t "$IMAGE" "$SCRIPT_DIR"
elif ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -t "$IMAGE" "$SCRIPT_DIR"
fi

tty_flags=(-i)
[[ -t 0 && -t 1 ]] && tty_flags=(-it)

mounts=(-v "$REPO_ROOT":/workspace)
[[ -d "$HOME/.aws" ]] && mounts+=(-v "$HOME/.aws":/root/.aws)
[[ -d "$HOME/.ssh" ]] && mounts+=(-v "$HOME/.ssh":/root/.ssh:ro)

exec docker run --rm "${tty_flags[@]}" \
  "${mounts[@]}" \
  -e AWS_PROFILE -e AWS_REGION -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e HF_TOKEN \
  -w /workspace \
  "$IMAGE" "${@:-bash}"
