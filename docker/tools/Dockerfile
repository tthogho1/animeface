# Operator toolbox: Terraform + Ansible + AWS CLI v2 for running the Makefile
# targets (infra / cluster / deploy) without installing them on the host.
# Built for the host's native arch (amd64 or arm64).
FROM python:3.12-slim-bookworm

ARG TERRAFORM_VERSION=1.9.8
ARG ANSIBLE_CORE_VERSION=2.17.7
ARG TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# openssh-client for Ansible, make/git for the repo Makefile.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip openssh-client make git \
    && rm -rf /var/lib/apt/lists/*

# Terraform: official release zip, verified against HashiCorp's SHA256SUMS.
RUN arch="${TARGETARCH:-$(dpkg --print-architecture)}" \
    && base="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}" \
    && zip="terraform_${TERRAFORM_VERSION}_linux_${arch}.zip" \
    && cd /tmp \
    && curl -fsSLO "${base}/${zip}" \
    && curl -fsSL "${base}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" | grep " ${zip}\$" | sha256sum -c - \
    && unzip -q "${zip}" -d /usr/local/bin \
    && rm -f "${zip}" \
    && terraform version

# AWS CLI v2 (Makefile `images` target and ECR login).
RUN case "${TARGETARCH:-$(dpkg --print-architecture)}" in \
        amd64) awsarch=x86_64 ;; arm64) awsarch=aarch64 ;; *) echo "unsupported arch" >&2; exit 1 ;; \
    esac \
    && cd /tmp \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${awsarch}.zip" -o awscliv2.zip \
    && unzip -q awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip \
    && aws --version

# ansible.cfg uses stdout_callback=yaml, which lives in community.general
# (removed in 12.x), so pin below that.
RUN pip install "ansible-core==${ANSIBLE_CORE_VERSION}" \
    && ansible-galaxy collection install -p /usr/share/ansible/collections "community.general:>=9,<12" \
    && ansible --version

WORKDIR /workspace
CMD ["bash"]
