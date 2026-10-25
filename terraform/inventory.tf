locals {
  ecr_registry = split("/", aws_ecr_repository.this["app"].repository_url)[0]
}

resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.ini"
  file_permission = "0644"
  content = templatefile("${path.module}/templates/hosts.ini.tftpl", {
    server               = { public_ip = aws_instance.server.public_ip, private_ip = aws_instance.server.private_ip }
    gpu_workers          = [for w in aws_instance.gpu : { public_ip = w.public_ip, private_ip = w.private_ip }]
    ssh_private_key_path = pathexpand(var.ssh_private_key_path)
  })
}

resource "local_file" "ansible_vars" {
  filename        = "${path.module}/../ansible/inventory/group_vars/all/terraform.yml"
  file_permission = "0644"
  content = templatefile("${path.module}/templates/terraform.yml.tftpl", {
    aws_region      = var.aws_region
    efs_id          = aws_efs_file_system.main.id
    efs_ap_models   = aws_efs_access_point.this["models"].id
    efs_ap_outputs  = aws_efs_access_point.this["outputs"].id
    ecr_registry    = local.ecr_registry
    comfyui_image   = aws_ecr_repository.this["comfyui"].repository_url
    app_image       = aws_ecr_repository.this["app"].repository_url
    server_publicip = aws_instance.server.public_ip
  })
}
