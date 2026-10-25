resource "aws_efs_file_system" "main" {
  encrypted = true
  # Elastic throughput avoids burst-credit starvation when loading 7GB checkpoints.
  throughput_mode = "elastic"

  tags = { Name = "${var.project}-efs" }
}

resource "aws_efs_mount_target" "main" {
  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = aws_subnet.public.id
  security_groups = [aws_security_group.efs.id]
}

# One access point per PVC; EFS creates the root directory on first use.
resource "aws_efs_access_point" "this" {
  for_each = toset(["models", "outputs"])

  file_system_id = aws_efs_file_system.main.id

  root_directory {
    path = "/${each.key}"
    creation_info {
      owner_uid   = 0
      owner_gid   = 0
      permissions = "755"
    }
  }

  tags = { Name = "${var.project}-${each.key}" }
}

resource "aws_ecr_repository" "this" {
  for_each = toset(["comfyui", "app"])

  name                 = "${var.project}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
