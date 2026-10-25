SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

TF       := terraform -chdir=terraform
TAG_FILE := .image-tag
KUBECTL  := KUBECONFIG=$(CURDIR)/kubeconfig kubectl -n animeface
TOOLS_IMAGE := animeface-tools

.PHONY: help init infra images cluster deploy up test ui logs destroy tools tools-shell

help:
	@echo "init     terraform init"
	@echo "infra    create AWS resources (VPC, EC2, EFS, ECR) + Ansible inventory"
	@echo "images   build & push ComfyUI and app images (linux/amd64) to ECR"
	@echo "cluster  install k3s, GPU/EFS add-ons, download models, deploy app"
	@echo "deploy   redeploy the app only (after 'make images')"
	@echo "up       infra + images + cluster"
	@echo "test     run app unit tests"
	@echo "ui       port-forward the ComfyUI editor to http://localhost:8188"
	@echo "logs     tail ComfyUI logs"
	@echo "destroy  tear everything down"
	@echo "tools        build the Terraform + Ansible + AWS CLI image ($(TOOLS_IMAGE))"
	@echo "tools-shell  shell in that image with the repo, ~/.aws and ~/.ssh mounted"

init:
	$(TF) init

infra:
	$(TF) apply

images:
	region=$$($(TF) output -raw aws_region); \
	registry=$$($(TF) output -raw ecr_registry); \
	tag=$$(date +%Y%m%d%H%M%S); \
	aws ecr get-login-password --region "$$region" | docker login --username AWS --password-stdin "$$registry"; \
	docker buildx build --platform linux/amd64 --push -t "$$($(TF) output -raw comfyui_repository_url):$$tag" docker/comfyui; \
	docker buildx build --platform linux/amd64 --push -t "$$($(TF) output -raw app_repository_url):$$tag" app; \
	echo "$$tag" > $(TAG_FILE); \
	echo "pushed tag $$tag"

cluster:
	cd ansible && ansible-playbook site.yml -e image_tag=$$(cat ../$(TAG_FILE))

deploy:
	cd ansible && ansible-playbook site.yml --tags app -e image_tag=$$(cat ../$(TAG_FILE))

up: infra images cluster

test:
	cd app && python3 -m pytest -q

ui:
	$(KUBECTL) port-forward svc/comfyui 8188:8188

logs:
	$(KUBECTL) logs -f deploy/comfyui

destroy:
	$(TF) destroy

tools:
	docker build -t $(TOOLS_IMAGE) docker/tools

tools-shell:
	docker/tools/start.sh
