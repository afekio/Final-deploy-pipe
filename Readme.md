## 1. The Application

The application is a multi-tier microservices architecture designed for high availability and security.

*   **Frontend:** A React Single Page Application (SPA) served by Nginx. The Nginx container is highly secured, running as a non-root user (UID 10001) on internal port 8080 while being exposed externally on port 80. It also acts as a private API Gateway, handling sub-path routing to backend APIs (`/api/`) and monitoring tools (`/grafana/`, `/prometheus/`).
*   **Backend & Auth Services:** Python/Flask-based REST APIs. The Auth service handles user registration and JWT-based authentication. The Backend service processes core application logic and infrastructure provisioning tasks[cite: 2].
*   **Database:** A robust PostgreSQL database managed by the CloudNativePG operator, providing automated backups and replication capabilities[cite: 2].
*   **Security Architecture:** The application operates under a strict "Default Deny" NetworkPolicy[cite: 2]. Microservices can only communicate with explicitly approved components, ensuring strict isolation between the frontend, backend, and database[cite: 2].

---

## 2. The Infrastructure

The underlying infrastructure is built to support production-grade Kubernetes workloads on raw instances.

*   **Kubernetes Engine:** Powered by RKE2 (Rancher Kubernetes Engine 2), providing a secure, lightweight, and CNCF-certified Kubernetes distribution[cite: 2].
*   **Networking:** MetalLB is deployed to provide proper LoadBalancer IP assignments on bare-metal environments[cite: 2].
*   **Storage:** An NFS Server provides dynamic storage provisioning[cite: 2]. It separates environments via StorageClasses: `nfs-dev` (deletes data when destroyed) and `nfs-prod` (retains data for safety)[cite: 2].
*   **Observability:** A dedicated monitoring stack (Prometheus and Grafana) is deployed alongside the application[cite: 2]. Data sources are auto-provisioned, and traffic is routed internally via the Frontend Nginx[cite: 2].

---

## 3. Infrastructure Automation (Ansible)

We use Ansible to completely automate the cluster setup. The playbook (`site.yml`) configures the base OS, installs RKE2, sets up the NFS mounts, applies MetalLB, and deploys Jenkins via Helm[cite: 2]. 

To keep sensitive data secure, the project relies on **Ansible Vault**[cite: 2]. 

**What you need to configure manually before running:**
1.  **Secrets:** You must create a plain text file named `.vault_pass` in the `ansible/` directory containing your vault password[cite: 2]. Then, populate `ansible/group_vars/.vault.yml` with your actual tokens and passwords[cite: 2].
2.  **Inventory:** Update `ansible/inventories/production/hosts.yml` with the actual IP addresses and SSH usernames of your target servers[cite: 2].
3.  **Network Variables:** Update `ansible/group_vars/all.yml` with your specific network interfaces, subnets, and DNS settings[cite: 2].

---

## 4. CI/CD Pipelines (Jenkins)

The repository includes two distinct Jenkins pipelines that handle the entire software lifecycle.

*   **Continuous Integration (`Jenkinsfile`):** 
    Triggered automatically on code changes. It performs unit testing on the Python code[cite: 2]. It then builds the Docker images for the Frontend, Backend, and Auth services using Kaniko (allowing rootless, daemonless builds inside Kubernetes)[cite: 2]. Finally, it scans the generated images for critical vulnerabilities using Trivy before pushing them to the container registry[cite: 2].
*   **Continuous Deployment (`Jenkinsfile-cd`):** 
    A parameterized deployment job. Based on the selected environment (`dev` or `prod`), it dynamically calculates the required replicas, storage classes, and namespace names[cite: 2]. It pulls central secrets from a vault, creates isolated namespaces, installs the CloudNativePG operator, and deploys the entire application stack via a unified Helm chart[cite: 2].

---

## 5. Step-by-Step Deployment Guide

Follow these steps to bring the entire platform online from scratch.

### Step 1: Prepare the Ansible Vault
Navigate to the ansible directory and set up your vault password file.
```bash
cd ansible
echo "your_secure_password" > .vault_pass

```

Edit the encrypted vault file to insert your actual passwords (e.g., Jenkins admin password, Docker registry token).

```bash
ansible-vault edit group_vars/.vault.yml --vault-password-file .vault_pass
```

### Step 2: Update Configuration Files
Edit inventories/production/hosts.yml and group_vars/all.yml to match your server IPs and network interfaces[cite: 2].

Step 3: Provision the Infrastructure
Run the main Ansible playbook. The -K flag will prompt you for the SSH sudo password of your target machines.

```bash
ansible-playbook site.yml -K --vault-password-file .vault_pass
```
Wait for this to complete. It will spin up RKE2, NFS, MetalLB, and Jenkins.

Step 4: Run Continuous Integration
Open the Jenkins UI (using the LoadBalancer IP assigned to it).

Log in with the admin credentials you defined in the vault[cite: 2].

Locate the CI-Images pipeline and click Build Now[cite: 2]. This will build, scan, and push your Docker images.

Step 5: Deploy the Application
In Jenkins, go to the CD-Environment pipeline[cite: 2].

Click Build with Parameters.

Select your target ENVIRONMENT (e.g., DEV or PROD) and provide the IMAGE_TAG generated by the CI process[cite: 2].

Click Build.

Once the pipeline finishes, your application, database, and monitoring stack will be live and accessible via the assigned LoadBalancer IP!

Happy deploying! If you encounter any issues, check the deployment logs in Jenkins or the Kubernetes pod events for quick troubleshooting.

### Accessing the System
Once the deployment pipeline finishes successfully, you need to find the LoadBalancer IP assigned to your environment. Run the following command and look for the `EXTERNAL-IP` of the `frontend` service:

```bash
kubectl get svc -n <your-environment-namespace>
```
Using that IP, you can access your newly provisioned environment:

Frontend Application: http://svc-IP/

Grafana Dashboards: http://svc-IP/grafana/

Default Username: admin

Default Password: admin

(Note: You will be prompted to change the Grafana password upon your first login for security reasons).

Happy deploying! If you encounter any issues, check the deployment logs in Jenkins or the Kubernetes pod events for quick troubleshooting.