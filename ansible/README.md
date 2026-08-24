# RKE2 & Jenkins CI/CD Infrastructure

This project uses Ansible to deploy an RKE2 Kubernetes cluster and a Jenkins CI/CD environment on existing machines. It configures the base OS, sets up the cluster, and provisions Jenkins with JCasC, including credentials and predefined pipelines.

## Repository Structure

*   `site.yml`: The main playbook that executes the roles in order.
*   `inventory/`: Contains the host inventory (Control Plane and Worker IPs).
*   `group_vars/`: Global and environment variables.
*   `vault_example.yml`: A template file for required secrets. Do not save real passwords here.
*   `roles/`: 
    *   `common`: Base configurations, networking, and DNS.
    *   `rke2`: RKE2 installation and cluster configuration.
    *   `jenkins`: Jenkins deployment, JCasC setup, credential injection, and automated job creation.

## Prerequisites

*   Target machines (e.g., Ubuntu) ready with SSH access and a public key configured.
*   Ansible installed on your control node.

## Deployment Instructions

### 1. Configure Secrets

You need to set up Ansible Vault to manage sensitive data like Jenkins admin passwords and tokens.

Copy the example vault file:
```bash
cp vault_example.yml vault.yml
Edit vault.yml and replace the placeholder values with your actual secrets.
```
Create a plain text file named vault_pass in the project root and type a strong password inside it. This password will be used to encrypt and decrypt your vault.

Encrypt the vault.yml file:

Bash
ansible-vault encrypt vault.yml --vault-password-file vault_pass
2. Run the Playbook
Execute the Ansible playbook to provision the infrastructure. The -K flag will prompt you for the sudo (become) password of the target machines.

Bash
ansible-playbook site.yml -K --vault-password-file vault_pass
Wait for the run to complete. This process sets up the entire RKE2 cluster and deploys Jenkins.

3. Execute the Application Pipeline
After the Ansible deployment finishes:

Access the Jenkins Web UI using the cluster's IP/LoadBalancer and the configured port.

Log in with the admin credentials you set in the vault.

On the main dashboard, locate the pre-configured job named Dev-Application-Pipeline.

Click Build Now.

The pipeline will automatically pull the code, build the container images, run Trivy security scans, and deploy the application resources to the RKE2 cluster.