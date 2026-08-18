import os
from datetime import datetime

def generate_tf_file(pydantic_model, logger, count: int, base_name: str, os_key: str):
    try:
        config_dir = "./Configs/Terraform"
        os.makedirs(config_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(config_dir, f"{base_name}_{timestamp}.tf")
        tf_content = f"""# Auto-generated Terraform Config for {base_name}
# Generated on: {timestamp}
# OS: {os_key.capitalize()}
# Instances Count: {count}

terraform {{
  required_providers {{
    proxmox = {{
      source  = "telmate/proxmox"
      version = "2.9.14"
    }}
  }}
}}

provider "proxmox" {{
  pm_api_url = "https://your-proxmox-server:8006/api2/json"
}}

resource "proxmox_vm_qemu" "{base_name}_nodes" {{
  count       = {count}
  name        = "{base_name}-${{count.index + 1}}"
  target_node = "pve"
  clone       = "{os_key}-template"
  os_type = "cloud-init"
  cores   = 2
  sockets = 1
  memory  = 2048
  network {{
    model  = "virtio"
    bridge = "vmbr0"
  }}
}}
"""
        with open(file_path, 'w') as tf_file:
            tf_file.write(tf_content)
        logger.info(f"Successfully generated Terraform file: {file_path}")
        return True, tf_content
    except Exception as e:
        logger.error(f"Failed to generate Terraform file. Error: {str(e)}")
        return False, ""
