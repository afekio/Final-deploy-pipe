pipeline {
  agent {
    kubernetes {
      defaultContainer 'jnlp'
      yaml '''
apiVersion: v1
kind: Pod
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
  containers:
    - name: jnlp
      image: <YOUR_JENKINS_AGENT_IMAGE>
    - name: kaniko
      image: <YOUR_KANIKO_IMAGE>
      command: ["/busybox/cat"]
      tty: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
    - name: trivy
      image: <YOUR_TRIVY_IMAGE>
      command: ["/bin/sh"]
      tty: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
    - name: helm
      image: <YOUR_HELM_IMAGE>
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
    pollSCM('H * * * *')
  }
  stages {
    stage('Checkout') {
      when {
        branch 'main'
      }
      steps { checkout scm }
    }
    stage('Build and test') {
      when { branch 'main' }
      steps {
        sh 'python3 -m compileall Auth Backend'
        sh 'python3 -m unittest discover -s . -p "test_*.py"'
      }
    }
    stage('Build images') {
      when { branch 'main' }
      steps {
        script {
          env.SHORT_SHA = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
        }
        container('kaniko') {
          withCredentials([usernamePassword(credentialsId: env.CICD_REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
            sh '''
              set -eu
              set +x
              mkdir -p /kaniko/.docker
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"%s":{"auth":"%s"}}}' "$CICD_REGISTRY" "$AUTH" > /kaniko/.docker/config.json
              for service in auth backend frontend; do
                /kaniko/executor \
                  --context "$WORKSPACE/$([ "$service" = frontend ] && echo Frontend || echo ${service^})" \
                  --dockerfile "$WORKSPACE/$([ "$service" = frontend ] && echo Frontend || echo ${service^})/dockerfile" \
                  --destination "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/$service:$SHORT_SHA"
              done
              rm -f /kaniko/.docker/config.json
            '''
          }
        }
      }
    }
    stage('Scan images') {
      when { branch 'main' }
      steps {
        container('trivy') {
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/auth:$SHORT_SHA"'
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/backend:$SHORT_SHA"'
          sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --no-progress "$CICD_REGISTRY/$CICD_IMAGE_NAMESPACE/frontend:$SHORT_SHA"'
        }
      }
    }
    stage('Deploy dev') {
      when { branch 'main' }
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
