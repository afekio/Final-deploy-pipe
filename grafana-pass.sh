#!/bin/bash

# Set the environment variable for RKE2 Kubeconfig path
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml

# Check if the Kubeconfig file exists and is readable
if [ ! -r "$KUBECONFIG" ]; then
    echo "Error: Cannot read RKE2 kubeconfig at $KUBECONFIG"
    echo "Please run this script as root or with sudo."
    exit 1
fi

# Add RKE2 binary path to PATH to ensure kubectl is available
export PATH=$PATH:/var/lib/rancher/rke2/bin

# Verify that kubectl command is accessible
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl command not found."
    exit 1
fi

# Find the namespace where a pod containing 'grafana' in its name is running
# This grabs the first matching namespace found in the cluster
NAMESPACE=$(kubectl get pods --all-namespaces --no-headers -o custom-columns=":metadata.namespace,:metadata.name" | grep "grafana" | awk '{print $1}' | head -n 1)

if [ -z "$NAMESPACE" ]; then
    echo "Error: No pod with name 'grafana' found in the cluster."
    exit 1
fi

# Find the Grafana secret name within that namespace (usually contains 'grafana')
SECRET_NAME=$(kubectl get secret -n "$NAMESPACE" --no-headers -o custom-columns=":metadata.name" | grep "grafana" | head -n 1)

if [ -z "$SECRET_NAME" ]; then
    echo "Error: Could not find a secret for Grafana in namespace $NAMESPACE."
    exit 1
fi

# Extract and decode the admin password from the secret
# Tries common keys like 'admin-password' first, then falls back to 'password'
PASSWORD=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath="{.data.admin-password}" 2>/dev/null | base64 --decode)

if [ -z "$PASSWORD" ]; then
    PASSWORD=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath="{.data.password}" 2>/dev/null | base64 --decode)
fi

if [ -z "$PASSWORD" ]; then
    echo "Error: Found secret $SECRET_NAME but could not extract admin password."
    exit 1
fi

# Print the final result in the requested NAMESPACE:PASSWORD format
echo "${NAMESPACE}:${PASSWORD}"
