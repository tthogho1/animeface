output "aws_region" {
  value = var.aws_region
}

output "server_public_ip" {
  value = aws_instance.server.public_ip
}

output "gpu_public_ips" {
  value = aws_instance.gpu[*].public_ip
}

output "app_url" {
  value = "http://${aws_instance.server.public_ip}/"
}

output "ecr_registry" {
  value = local.ecr_registry
}

output "comfyui_repository_url" {
  value = aws_ecr_repository.this["comfyui"].repository_url
}

output "app_repository_url" {
  value = aws_ecr_repository.this["app"].repository_url
}

output "efs_id" {
  value = aws_efs_file_system.main.id
}
