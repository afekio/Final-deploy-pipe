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
        image: afekio/rke2-kaniko-rke2:1.3
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
            sh '''#!/bin/bash
                            set -eu
                            
                            # --- FIX FOR KANIKO IPv6 ISSUE ---
                            # Force Docker Hub domains to resolve to IPv4 only by adding them to /etc/hosts inside the pod
                            echo "$(getent ahostsv4 auth.docker.io | awk 'NR==1 {print $1}') auth.docker.io" >> /etc/hosts
                            echo "$(getent ahostsv4 registry-1.docker.io | awk 'NR==1 {print $1}') registry-1.docker.io" >> /etc/hosts
                            echo "$(getent ahostsv4 index.docker.io | awk 'NR==1 {print $1}') index.docker.io" >> /etc/hosts
                            # ---------------------------------
                            
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
    // Part 2: CD - Deploy with Ansible
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
sh '''#!/bin/bash
                set -eu
                
                # --- THE REAL FIX FOR KANIKO IPv6 ---
                # Turn off IPv6 inside this specific pod only. 
                # This forces Kaniko to use IPv4 for everything.
                sysctl -w net.ipv6.conf.all.disable_ipv6=1 2>/dev/null || echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6 || true
                
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
  }
}