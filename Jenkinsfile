pipeline {
  agent {
    kubernetes {
      defaultContainer 'jnlp'
      yaml '''
apiVersion: v1
kind: Pod
spec:
  restartPolicy: Never
  dnsConfig:
    options:
      - name: ndots
        value: "1"
      - name: single-request-reopen
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
  containers:
    - name: jnlp
      image: jenkins/inbound-agent:latest
    - name: python
      image: python:3.11-slim
      command: ["/bin/sh"]
      tty: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
    - name: buildkit
      # Using the official BuildKit image
      image: moby/buildkit:latest
      command: ["/bin/sh", "-c", "sleep 9999999"]
      tty: true
      securityContext:
        # BuildKit requires privileged mode AND root access to handle network namespaces and overlayfs
        privileged: true
        runAsNonRoot: false
        runAsUser: 0
    - name: trivy
      image: aquasec/trivy:latest
      command: ["/bin/sh"]
      tty: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
    - name: helm
      image: alpine/helm:latest
      command: ["/bin/sh"]
      tty: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
      '''
      podRetention never()
      idleMinutes 0
    }
  }
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }
  triggers {
    pollSCM('* * * * *')
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Build and test') {
      steps {
        container('python') {
          sh 'python3 -m compileall Auth Backend'
          sh 'python3 -m unittest discover -s . -p "test_*.py"'
        }
      }
    }
    stage('Build images') {
      steps {
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
        }
        container('buildkit') {
          withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
            sh '''
              set -eu
              set +x
              
              # Run ping test and save to log
              echo "Executing ping test..."
              curl https://wtfismyip.com/json -o "$WORKSPACE/ping-result.log" 2>&1 || true
              
              # Setup Docker configuration directory for BuildKit authentication in WORKSPACE
              export DOCKER_CONFIG="$WORKSPACE/.docker"
              mkdir -p "$DOCKER_CONFIG"
              
              # Authenticate to Docker Hub using injected Jenkins credentials
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
              
              # Loop through microservices, build, and push to the registry using BuildKit
              for dir in Auth Backend Frontend; do
                service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
                
                echo "Building and pushing ${service} with BuildKit..."
                
                # buildctl-daemonless.sh safely starts the engine, builds, pushes, and stops
                buildctl-daemonless.sh build \
                  --frontend dockerfile.v0 \
                  --local context="$WORKSPACE/$dir" \
                  --local dockerfile="$WORKSPACE/$dir" \
                  --output type=image,name="$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:${service}-$SHORT_SHA",push=true
              done
              
              # Clean up credentials
              rm -f "$DOCKER_CONFIG/config.json"
            '''
          }
        }
      }
      post {
        always {
          // Archive the ping result log so it can be viewed in Jenkins UI
          archiveArtifacts artifacts: 'ping-result.log', allowEmptyArchive: true
        }
      }
    }
    stage('Scan images') {
      steps {
        container('trivy') {
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:auth-$SHORT_SHA"'
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:backend-$SHORT_SHA"'
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:frontend-$SHORT_SHA"'
        }
      }
    }
    stage('Deploy dev') {
      steps {
        withCredentials([file(credentialsId: env.CICD_KUBECONFIG_CREDENTIALS_ID, variable: 'KUBECONFIG_FILE')]) {
          container('helm') {
            sh '''
              set -eu
              set +x
              
              export KUBECONFIG="$KUBECONFIG_FILE"
              
              kubectl apply -f deploy/dev/namespaces-pvcs.yaml
              
              sed -e "s#<YOUR_REGISTRY>#$CICD_REGISTRY#g" \
                  -e "s#<YOUR_IMAGE_NAMESPACE>#$CICD_IMAGE_NAMESPACE#g" \
                  -e "s#<YOUR_IMAGE_TAG>#$SHORT_SHA#g" \
                  deploy/dev/application.yaml > "$WORKSPACE/application.rendered.yaml"
                  
              helm repo add cloudnative-pg "$CICD_CNPG_CHART_REPO_URL" --force-update
              helm repo update cloudnative-pg
              
              helm upgrade --install cnpg cloudnative-pg/cloudnative-pg \
                --namespace cnpg-system --create-namespace \
                --values deploy/dev/cnpg-operator-values.yaml --wait --timeout 10m
                
              kubectl apply -f deploy/dev/cnpg-cluster.yaml
              kubectl apply -f deploy/dev/networkpolicies.yaml
              kubectl apply -f "$WORKSPACE/application.rendered.yaml"
              
              kubectl -n dev-postgres wait --for=condition=Ready cluster/dev-postgres --timeout=15m
            '''
          }
        }
      }
    }
  }
}