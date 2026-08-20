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
    - name: kaniko
      # Ensure you are using the Ubuntu-based Kaniko image that has bash and ping installed
      image: afekio/rke2-kaniko-rke2:1.0
      # Keep the container alive using bash so Jenkins can attach
      command: ["/bin/bash", "-c", "sleep infinity"]
      tty: true
      securityContext:
        # Kaniko must run as root to build containers and modify the filesystem
        runAsNonRoot: false
        runAsUser: 0
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
          add: ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETUID", "SETGID"]
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
        container('kaniko') {
          withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
            sh '''
              set -eu
              set +x
              
              # Run the ping test and save the output to a log file
              # Using || true so the pipeline continues even if ping fails
              echo "Executing ping test..."
              ping 8.8.8.8 -c 3 > "$WORKSPACE/ping-result.log" 2>&1 || true
              
              # Fix DNS resolution bug for Kaniko in Kubernetes
              echo 'hosts: files dns' > /etc/nsswitch.conf
              
              # Setup Docker configuration directory
              export DOCKER_CONFIG="$WORKSPACE/.docker"
              mkdir -p "$DOCKER_CONFIG"
              
              # Authenticate to Docker Hub using injected Jenkins credentials
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
              
              # Loop through microservices, build, and push to the registry
              for dir in Auth Backend Frontend; do
                service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
                
                /kaniko/executor \
                  --context "$WORKSPACE/$dir" \
                  --dockerfile "$WORKSPACE/$dir/dockerfile" \
                  --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:${service}-$SHORT_SHA"
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
          // Scan the newly built images for high and critical vulnerabilities
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
              
              # Apply namespace and PVCs
              kubectl apply -f deploy/dev/namespaces-pvcs.yaml
              
              # Render the application manifest with the new image tags
              sed -e "s#<YOUR_REGISTRY>#$CICD_REGISTRY#g" \
                  -e "s#<YOUR_IMAGE_NAMESPACE>#$CICD_IMAGE_NAMESPACE#g" \
                  -e "s#<YOUR_IMAGE_TAG>#$SHORT_SHA#g" \
                  deploy/dev/application.yaml > "$WORKSPACE/application.rendered.yaml"
                  
              # Add and update the CloudNativePG Helm repository
              helm repo add cloudnative-pg "$CICD_CNPG_CHART_REPO_URL" --force-update
              helm repo update cloudnative-pg
              
              # Deploy the CloudNativePG operator
              helm upgrade --install cnpg cloudnative-pg/cloudnative-pg \
                --namespace cnpg-system --create-namespace \
                --values deploy/dev/cnpg-operator-values.yaml --wait --timeout 10m
                
              # Apply the cluster, network policies, and the main application
              kubectl apply -f deploy/dev/cnpg-cluster.yaml
              kubectl apply -f deploy/dev/networkpolicies.yaml
              kubectl apply -f "$WORKSPACE/application.rendered.yaml"
              
              # Wait for the PostgreSQL cluster to become ready
              kubectl -n dev-postgres wait --for=condition=Ready cluster/dev-postgres --timeout=15m
            '''
          }
        }
      }
    }
  }
}