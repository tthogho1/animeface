variable "project" {
  description = "Name prefix for all resources."
  type        = string
  default     = "animeface"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-northeast-1"
}

variable "availability_zone" {
  description = "AZ for nodes and EFS mount target. Empty = first AZ in the region. Pick one where the GPU instance type is available."
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "allowed_cidrs" {
  description = "CIDRs allowed to reach SSH (22), the Kubernetes API (6443) and the web app (80/443). Use your own IP, e.g. [\"203.0.113.10/32\"]."
  type        = list(string)
}

variable "ssh_public_key_path" {
  description = "Public key registered as the EC2 key pair."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "ssh_private_key_path" {
  description = "Matching private key, written into the Ansible inventory."
  type        = string
  default     = "~/.ssh/id_ed25519"
}

variable "server_instance_type" {
  description = "Instance type of the k3s control-plane node (CPU only)."
  type        = string
  default     = "t3.medium"
}

variable "server_root_volume_gb" {
  description = "Root volume size of the control-plane node."
  type        = number
  default     = 40
}

variable "gpu_instance_type" {
  description = "Instance type of the GPU workers. g5.xlarge = 1x A10G 24GB."
  type        = string
  default     = "g5.xlarge"
}

variable "gpu_worker_count" {
  description = "Number of GPU worker nodes. Set to 0 to stop GPU spend while keeping the rest."
  type        = number
  default     = 1
}

variable "gpu_root_volume_gb" {
  description = "Root volume size of GPU workers (holds the ~10GB ComfyUI image)."
  type        = number
  default     = 150
}
