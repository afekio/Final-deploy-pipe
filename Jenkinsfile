pipeline {
  agent none
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }
  stages {
    stage('CI - Build and Scan') {
      agent {
        kubernetes {
          defaultContainer 'jnlp'
          yaml '''
  apiVersion: v1
  kind: Pod
  spec:
    restartPolicy: Never
    containers:
      - name: jnlp
        image: afekio/rke2-kanikoamd-rke2:1.0
        tty: true
        securityContext:
          privileged: true
          runAsUser: 0
          '''
          podRetention never()
          idleMinutes 0
        }
      }
      stages {
        stage('Checkout') {
          steps { checkout scm }
        }
        
        stage('Build and test') {
          steps {
            sh 'python3 -m compileall Auth Backend'
            sh 'python3 -m unittest discover -s . -p "test_*.py"'
          }
        }
        
        stage('Build and push images') {
          steps {
            script {
              // 1. Fetch tags from Git to ensure Jenkins knows about them
              sh 'git fetch --tags || true'
              
              // 2. Try to get the exact tag for this commit. If it fails, fallback to Short SHA
              env.EXACT_TAG = sh(script: 'git describe --tags --exact-match HEAD 2>/dev/null || echo ""', returnStdout: true).trim()
              env.IMAGE_TAG = env.EXACT_TAG ? env.EXACT_TAG : sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
              
              echo "======================================================"
              echo "Detected Image Tag for Build: ${env.IMAGE_TAG}"
              echo "======================================================"
            }
            withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
            sh '''#!/bin/bash
              set -eu
              
              # --- THE ULTIMATE OS-LEVEL IPv4 FIX ---
              echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf || true
              export GODEBUG=netdns=cgo
              # --------------------------------------
              
              export DOCKER_CONFIG="$WORKSPACE/.docker"
              mkdir -p "$DOCKER_CONFIG"
              
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\n')
              printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
              
              # Build distinct images with the resolved IMAGE_TAG
              for dir in Auth Backend Frontend; do
                service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
                /kaniko/executor \
                  --context "$WORKSPACE/$dir" \
                  --dockerfile "$WORKSPACE/$dir/dockerfile" \
                  --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-${service}:$IMAGE_TAG"
              done
              
              rm -f "$DOCKER_CONFIG/config.json"
            '''
            }
          }
        }
        
        stage('Scan images') {
          steps {
            sh '''#!/bin/bash
              set -eu
              
              # --- THE ULTIMATE OS-LEVEL IPv4 FIX ---
              echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf || true
              export GODEBUG=netdns=cgo
              # --------------------------------------
              
              export TRIVY_CACHE_DIR="$WORKSPACE/.trivy-cache"
              mkdir -p "$TRIVY_CACHE_DIR"
              
              # Scan the images using the dynamically resolved IMAGE_TAG
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-auth:$IMAGE_TAG"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-backend:$IMAGE_TAG"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-frontend:$IMAGE_TAG"
            '''
          }
        }
      }
    }
  }
}