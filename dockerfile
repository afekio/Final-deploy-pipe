# 1. Base Image
FROM ubuntu:22.04

# Prevent interactive prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# 2. Install prerequisites, Python, and Java (Required for Jenkins JNLP/Remoting)
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    python3 \
    python3-pip \
    curl \
    wget \
    git \
    unzip \
    tar \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Trivy (for image scanning)
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# 4. Install Helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
    && bash get_helm.sh && rm get_helm.sh

# 5. Install Kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# 6. Bring in Kaniko and Busybox
# The Jenkinsfile explicitly calls /busybox/sh and /kaniko/executor.
# We copy them directly from the official Kaniko 'debug' image so your scripts work exactly as written.
COPY --from=gcr.io/kaniko-project/executor:debug /kaniko /kaniko
COPY --from=gcr.io/kaniko-project/executor:debug /busybox /busybox

# 7. Bring in Jenkins Agent (JNLP) files
COPY --from=jenkins/inbound-agent:latest /usr/local/bin/jenkins-agent /usr/local/bin/jenkins-agent
COPY --from=jenkins/inbound-agent:latest /usr/share/jenkins/agent.jar /usr/share/jenkins/agent.jar

# Set SSL certs path for Kaniko
ENV SSL_CERT_DIR=/etc/ssl/certs

# Kaniko requires ROOT to build images, and your script uses 'mount --bind' which also requires root.
USER root

# Start the Jenkins agent
ENTRYPOINT ["/usr/local/bin/jenkins-agent"]