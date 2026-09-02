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
        image: afekio/rke2-kaniko-rke2:1.2
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
              env.SHORT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
            }
            withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
            sh '''#!/bin/bash
              set -eu
              
              # --- THE ULTIMATE OS-LEVEL IPv4 FIX ---
              # Configure Ubuntu's glibc resolver to prioritize IPv4 addresses over IPv6.
              # This completely avoids 404s, DNS manipulation, and network unreachable errors.
              echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf || true
              export GODEBUG=netdns=cgo
              # --------------------------------------
              
              export DOCKER_CONFIG="$WORKSPACE/.docker"
              mkdir -p "$DOCKER_CONFIG"
              
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
              
              # Build distinct images for each service with the rke2- prefix
              for dir in Auth Backend Frontend; do
                service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
                /kaniko/executor \
                  --context "$WORKSPACE/$dir" \
                  --dockerfile "$WORKSPACE/$dir/dockerfile" \
                  --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-${service}:$SHORT_SHA"
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
              
              # Scan the corrected image names with rke2- prefix
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-auth:$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-backend:$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2-frontend:$SHORT_SHA"
            '''
          }
        }
      }
    }
  }
}