#!/bin/bash

set -euo pipefail

# Set the environment variable for RKE2 Kubeconfig path
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml

# Check if the Kubeconfig file exists and is readable
if [[ ! -r "$KUBECONFIG" ]]; then
    echo "Error: Cannot read RKE2 kubeconfig at $KUBECONFIG" >&2
    echo "Please run this script as root or with sudo." >&2
    exit 1
fi

# Add RKE2 binary path to PATH to ensure kubectl is available
export PATH="$PATH:/var/lib/rancher/rke2/bin"

# Verify that kubectl command is accessible
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl command not found." >&2
    exit 1
fi

NAMESPACES=$(kubectl get pods --all-namespaces --no-headers -o custom-columns=":metadata.namespace,:metadata.name" \
    | awk 'tolower($2) ~ /grafana/ {print $1}' \
    | sort -u || true)

if [[ -z "$NAMESPACES" ]]; then
    echo "Error: No pod with name 'grafana' found in the cluster." >&2
    exit 1
fi

decode_secret_key() {
    local namespace="$1"
    local secret_name="$2"
    local key="$3"

    kubectl get secret "$secret_name" -n "$namespace" -o go-template="{{ index .data \"${key}\" }}" 2>/dev/null \
        | base64 --decode 2>/dev/null || true
}

guess_environment() {
    local namespace="$1"

    if [[ "$namespace" == prod* || "$namespace" == *-prod-* ]]; then
        echo "prod"
    elif [[ "$namespace" == dev* || "$namespace" == *-dev-* ]]; then
        echo "dev"
    else
        echo "unknown"
    fi
}

printf '%-36s %-8s %-32s %-28s %s\n' "NAMESPACE" "ENV" "POD" "SOURCE" "PASSWORD"
printf '%-36s %-8s %-32s %-28s %s\n' "---------" "---" "---" "------" "--------"

# מעבר בלולאה על כל Namespace שנמצא
echo "$NAMESPACES" | while read -r NAMESPACE; do
    [[ -z "$NAMESPACE" ]] && continue

    ENVIRONMENT=$(guess_environment "$NAMESPACE")
    PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers -o custom-columns=":metadata.name" \
        | awk 'tolower($1) ~ /grafana/ {print $1}' || true)

    echo "$PODS" | while read -r POD_NAME; do
        [[ -z "$POD_NAME" ]] && continue

        PASSWORD=""
        SOURCE="grafana-default"

        ENV_LINES=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
            -o jsonpath='{range .spec.containers[*].env[*]}{.name}{"|"}{.value}{"|"}{.valueFrom.secretKeyRef.name}{"|"}{.valueFrom.secretKeyRef.key}{"\n"}{end}' 2>/dev/null || true)

        while IFS='|' read -r ENV_NAME ENV_VALUE SECRET_NAME SECRET_KEY; do
            [[ "$ENV_NAME" != "GF_SECURITY_ADMIN_PASSWORD" ]] && continue

            if [[ -n "$ENV_VALUE" ]]; then
                PASSWORD="$ENV_VALUE"
                SOURCE="env:GF_SECURITY_ADMIN_PASSWORD"
                break
            fi

            if [[ -n "$SECRET_NAME" && -n "$SECRET_KEY" ]]; then
                PASSWORD=$(decode_secret_key "$NAMESPACE" "$SECRET_NAME" "$SECRET_KEY")
                SOURCE="secret:${SECRET_NAME}/${SECRET_KEY}"
                break
            fi
        done <<< "$ENV_LINES"

        if [[ -z "$PASSWORD" ]]; then
            for SECRET_NAME in $(kubectl get secrets -n "$NAMESPACE" --no-headers -o custom-columns=":metadata.name" \
                | awk 'tolower($1) ~ /(grafana|admin)/ {print $1}' || true); do
                for SECRET_KEY in admin-password password; do
                    PASSWORD=$(decode_secret_key "$NAMESPACE" "$SECRET_NAME" "$SECRET_KEY")
                    if [[ -n "$PASSWORD" ]]; then
                        SOURCE="secret:${SECRET_NAME}/${SECRET_KEY}"
                        break 2
                    fi
                done
            done
        fi

        if [[ -z "$PASSWORD" ]]; then
            PASSWORD="admin"
        fi

        printf '%-36s %-8s %-32s %-28s %s\n' "$NAMESPACE" "$ENVIRONMENT" "$POD_NAME" "$SOURCE" "$PASSWORD"
    done
done
