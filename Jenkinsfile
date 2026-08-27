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
  # Ensure the pod runs as root to allow the mount bind hack for DNS
  securityContext:
    runAsUser: 0
    runAsGroup: 0
    fsGroup: 0
  containers:
    - name: jnlp
      # REPLACE THIS with the actual registry/image name where you pushed the new Dockerfile
      image: afekio/rke2-kaniko-rke2:1.1
      pullPolicy: Always
      tty: true
      securityContext:
        privileged: true # Required for mount --bind
        runAsUser: 0
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
        // Runs directly in the main container using the installed Python
        sh 'python3 -m compileall Auth Backend'
        sh 'python3 -m unittest discover -s . -p "test_*.py"'
      }
    }
    stage('Build images') {
      steps {
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
        }
        withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
          // Using busybox shell explicitly for Kaniko compatibility
          sh '''#!/busybox/sh
            set -eu
            set +x
            
            # --- THE DNS BYPASS HACK FOR KANIKO ---
            echo "Overriding cluster DNS with Google DNS..."
            echo "nameserver 8.8.8.8" > "$WORKSPACE/resolv.conf.override"
            echo "nameserver 1.1.1.1" >> "$WORKSPACE/resolv.conf.override"
            /busybox/mount --bind "$WORKSPACE/resolv.conf.override" /etc/resolv.conf
            
            export DOCKER_CONFIG="$WORKSPACE/.docker"
            mkdir -p "$DOCKER_CONFIG"
            
            AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
            printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
            
            for dir in Auth Backend Frontend; do
              service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
              
              echo "Building and pushing ${service} with Kaniko..."
              
              /kaniko/executor \
                --context "$WORKSPACE/$dir" \
                --dockerfile "$WORKSPACE/$dir/dockerfile" \
                --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:${service}-$SHORT_SHA"
            done
            
            rm -f "$DOCKER_CONFIG/config.json"
          '''
        }
      }
    }
    stage('Scan images') {
      steps {
        // Runs directly using the installed Trivy
        sh '''
          set -eu
          set +x
          
          # --- THE DNS BYPASS HACK FOR TRIVY ---
          echo "Overriding cluster DNS with Google DNS..."
          echo "nameserver 8.8.8.8" > "$WORKSPACE/resolv.conf.override"
          echo "nameserver 1.1.1.1" >> "$WORKSPACE/resolv.conf.override"
          mount --bind "$WORKSPACE/resolv.conf.override" /etc/resolv.conf
          
          # Use Workspace for Trivy Cache
          export TRIVY_CACHE_DIR="$WORKSPACE/.trivy-cache"
          mkdir -p "$TRIVY_CACHE_DIR"
          # exit-code 0 allows the pipeline to continue even if vulnerabilities are found
          trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:auth-$SHORT_SHA"
          trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:backend-$SHORT_SHA"
          trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:frontend-$SHORT_SHA"
        '''
      }
    }
    stage('Deploy dev') {
      steps {
        withCredentials([file(credentialsId: env.CICD_KUBECONFIG_CREDENTIALS_ID, variable: 'KUBECONFIG_FILE')]) {
          // Runs directly using the installed Helm and Kubectl
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