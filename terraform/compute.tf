resource "aws_key_pair" "main" {
  key_name   = "${var.project}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Ships with the NVIDIA driver and nvidia-container-toolkit, which k3s
# detects automatically to register the "nvidia" containerd runtime.
data "aws_ami" "gpu" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04) *"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  # Pods (EFS CSI driver) need IMDSv2 reachable through one extra network hop.
  metadata_hop_limit = 2
}

resource "aws_instance" "server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.server_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.nodes.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.node.name

  root_block_device {
    volume_size = var.server_root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = local.metadata_hop_limit
  }

  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = "${var.project}-k3s-server" }
}

resource "aws_instance" "gpu" {
  count = var.gpu_worker_count

  ami                    = data.aws_ami.gpu.id
  instance_type          = var.gpu_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.nodes.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.node.name

  root_block_device {
    volume_size = var.gpu_root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = local.metadata_hop_limit
  }

  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = "${var.project}-gpu-${count.index}" }
}
