pipeline {
  // Disable global agent so we can define specific agents for each stage
  agent none 
  
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  stages {
    // ==========================================
    // Part 1: CI - Runs inside the ephemeral Kubernetes pod
    // ==========================================
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
        # Using the updated image with Java 21 and Ansible
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
        stage('Build images') {
          steps {
            script {
              // Save the variable globally so it is available for the Deploy stage later
              env.SHORT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
            }
            withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
              sh '''#!/busybox/sh
                set -eu
                
                export DOCKER_CONFIG="$WORKSPACE/.docker"
                mkdir -p "$DOCKER_CONFIG"
                
                AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
                printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}, "index.docker.io":{"auth":"%s"}, "docker.io":{"auth":"%s"}, "registry-1.docker.io":{"auth":"%s"}}}' "$AUTH" "$AUTH" "$AUTH" "$AUTH" > "$DOCKER_CONFIG/config.json"
                
                for dir in Auth Backend Frontend; do
                  service=$(echo "$dir" | tr '[:upper:]' '[:lower:]')
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
            sh '''
              set -eu
              export TRIVY_CACHE_DIR="$WORKSPACE/.trivy-cache"
              mkdir -p "$TRIVY_CACHE_DIR"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:auth-$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:backend-$SHORT_SHA"
              trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/rke2:frontend-$SHORT_SHA"
            '''
          }
        }
      }
    } // The ephemeral Kubernetes pod is completely destroyed here!

    // ==========================================
    // Part 2: CD - Runs locally on the Jenkins Master
    // ==========================================
    stage('CD - Deploy with Ansible') {
      agent {
        // In newer Jenkins versions this is 'built-in', in older ones it is 'master'
        label 'built-in' 
      }
      steps {
        // We pull the code again because we switched machines (from the pod to the master node)
        checkout scm
        
        withCredentials([file(credentialsId: env.CICD_KUBECONFIG_CREDENTIALS_ID, variable: 'KUBECONFIG_FILE')]) {
          sh '''
            set -eu
            export KUBECONFIG="$KUBECONFIG_FILE"
            
            echo "Running Ansible Playbook locally on Jenkins Master..."
            ansible-playbook deploy/dev/deploy-app.yml \
              -e "image_registry=$CICD_REGISTRY" \
              -e "image_namespace=$CICD_IMAGE_NAMESPACE" \
              -e "image_tag=$SHORT_SHA"
          '''
        }
      }
    }
  }
}