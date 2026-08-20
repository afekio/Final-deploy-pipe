# Stage 1: Get Kaniko binaries from the official image
FROM gcr.io/kaniko-project/executor:debug AS kaniko

# Stage 2: Use Ubuntu as the stable base OS
FROM ubuntu:24.04
USER root
# Install networking debugging tools and security certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    dnsutils \
    ca-certificates \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy Kaniko files from the first stage
COPY --from=kaniko /kaniko /kaniko

# Configure environment variables required by Kaniko
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/kaniko"
ENV DOCKER_CONFIG="/kaniko/.docker"
ENV SSL_CERT_DIR="/etc/ssl/certs"

# Keep the container alive for Jenkins to attach
CMD ["/bin/bash", "-c", "sleep infinity"]