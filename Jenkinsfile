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
              
              # --- FIX FOR DOCKER HUB & PYTHON PIP IPv6 ISSUE ---
              echo "$(getent ahostsv4 auth.docker.io | awk 'NR==1 {print $1}') auth.docker.io" >> /etc/hosts || true
              echo "$(getent ahostsv4 registry-1.docker.io | awk 'NR==1 {print $1}') registry-1.docker.io" >> /etc/hosts || true
              echo "$(getent ahostsv4 index.docker.io | awk 'NR==1 {print $1}') index.docker.io" >> /etc/hosts || true
              echo "$(getent ahostsv4 production.cloudfront.docker.com | awk 'NR==1 {print $1}') production.cloudfront.docker.com" >> /etc/hosts || true
              echo "$(getent ahostsv4 pypi.org | awk 'NR==1 {print $1}') pypi.org" >> /etc/hosts || true
              echo "$(getent ahostsv4 pypi.python.org | awk 'NR==1 {print $1}') pypi.python.org" >> /etc/hosts || true
              echo "$(getent ahostsv4 files.pythonhosted.org | awk 'NR==1 {print $1}') files.pythonhosted.org" >> /etc/hosts || true
              # --------------------------------------------------
              
              export DOCKER_CONFIG="$WORKSPACE/.docker"
              mkdir -p "$DOCKER_CONFIG"
              
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
              
              # Build distinct images for each service
              for dir in Auth Backend Frontend; do
                service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
                /kaniko/executor \\
                  --context "$WORKSPACE/$dir" \\
                  --dockerfile "$WORKSPACE/$dir/dockerfile" \\
                  --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/${service}:$SHORT_SHA"
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
              
              # --- FIX FOR TRIVY CDN & DB IPv6 ISSUE ---
              echo "$(getent ahostsv4 production.cloudfront.docker.com | awk 'NR==1 {print $1}') production.cloudfront.docker.com" >> /etc/hosts || true
              echo "$(getent ahostsv4 mirror.gcr.io | awk 'NR==1 {print $1}') mirror.gcr.io" >> /etc/hosts || true
              echo "$(getent ahostsv4 ghcr.io | awk 'NR==1 {print $1}') ghcr.io" >> /etc/hosts || true
              echo "$(getent ahostsv4 pkg-containers.githubusercontent.com | awk 'NR==1 {print $1}') pkg-containers.githubusercontent.com" >> /etc/hosts || true
              
              export TRIVY_CACHE_DIR="$WORKSPACE/.trivy-cache"
              mkdir -p "$TRIVY_CACHE_DIR"
              
              # Scan the corrected image names
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/auth:$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/backend:$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/frontend:$SHORT_SHA"
            '''
          }
        }
      }
    }
  }
}