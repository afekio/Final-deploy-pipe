pipeline {
  agent none

  options {
    timestamps()
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    buildDiscarder(logRotator(numToKeepStr: '50'))
  }

  environment {
    IMAGE_REPOSITORY = '<YOUR_DOCKER_REGISTRY>/<YOUR_IMAGE_REPOSITORY>'
    HELM_RELEASE = '<YOUR_HELM_RELEASE_NAME>'
    HELM_CHART_PATH = '<YOUR_HELM_CHART_PATH>'
    DEV_NAMESPACE = '<YOUR_DEV_NAMESPACE>'
    STAGE_NAMESPACE = '<YOUR_STAGE_NAMESPACE>'
    PROD_NAMESPACE = '<YOUR_PROD_NAMESPACE>'
    KUBECONFIG_CREDENTIALS_ID = '<YOUR_KUBECONFIG_CREDENTIALS_ID>'
    REGISTRY_CREDENTIALS_ID = '<YOUR_DOCKER_REGISTRY_CREDENTIALS_ID>'
    GITHUB_TOKEN_CREDENTIALS_ID = '<YOUR_GITHUB_TOKEN_CREDENTIALS_ID>'
  }

  stages {
    stage('Checkout') {
      when {
        not { buildingTag() }
      }
      steps {
        checkout scm
      }
    }

    stage('PR checks') {
      when {
        changeRequest()
      }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      stages {
        stage('Lint') {
          steps {
            sh 'python -m compileall Auth Backend'
          }
        }
        stage('Unit tests') {
          steps {
            sh 'python -m unittest discover -s . -p "test_*.py"'
          }
        }
        stage('SAST and secret scan') {
          steps {
            container('trivy') {
              sh 'trivy fs --scanners vuln,secret,misconfig --exit-code 1 --no-progress .'
            }
          }
        }
      }
    }

    stage('Build image') {
      when {
        anyOf {
          branch 'main'
          buildingTag()
        }
      }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      steps {
        script {
          env.IMAGE_TAG = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
          if (env.TAG_NAME) {
            env.IMAGE_TAG = env.TAG_NAME.replaceAll('[^A-Za-z0-9_.-]', '-')
          }
        }
        container('kaniko') {
          withCredentials([usernamePassword(
            credentialsId: env.REGISTRY_CREDENTIALS_ID,
            usernameVariable: 'REGISTRY_USER',
            passwordVariable: 'REGISTRY_PASSWORD'
          )]) {
            sh '''
              set +x
              mkdir -p /kaniko/.docker
              AUTH=$(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\\n')
              printf '{"auths":{"<YOUR_DOCKER_REGISTRY>":{"auth":"%s"}}}' "$AUTH" > /kaniko/.docker/config.json
              /kaniko/executor --context "$WORKSPACE" --dockerfile "$WORKSPACE/<YOUR_DOCKERFILE_PATH>" \
                --destination "$IMAGE_REPOSITORY:$IMAGE_TAG" --cache=true --cache-dir=/cache/kaniko
              rm -f /kaniko/.docker/config.json
            '''
          }
        }
      }
    }

    stage('Trivy image scan') {
      when {
        anyOf {
          branch 'main'
          buildingTag()
        }
      }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      steps {
        container('trivy') {
          withCredentials([usernamePassword(
            credentialsId: env.REGISTRY_CREDENTIALS_ID,
            usernameVariable: 'REGISTRY_USER',
            passwordVariable: 'REGISTRY_PASSWORD'
          )]) {
            sh 'trivy image --username "$REGISTRY_USER" --password "$REGISTRY_PASSWORD" --exit-code 1 --severity HIGH,CRITICAL --no-progress "$IMAGE_REPOSITORY:$IMAGE_TAG"'
          }
        }
      }
    }

    stage('Deploy Dev') {
      when { branch 'main' }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      steps {
        deployHelm(env.DEV_NAMESPACE)
      }
    }

    stage('Deploy Stage') {
      when { buildingTag() }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      steps {
        deployHelm(env.STAGE_NAMESPACE)
      }
    }

    stage('Approve Production') {
      when { buildingTag() }
      steps {
        input message: 'Deploy this release to production?', ok: 'Deploy', submitter: '<YOUR_PRODUCTION_APPROVERS>'
      }
    }

    stage('Deploy Prod') {
      when { buildingTag() }
      agent {
        kubernetes {
          yamlFile 'ci/jenkins-agent.yaml'
          defaultContainer 'jnlp'
          podRetention never()
          idleMinutes 0
        }
      }
      steps {
        deployHelm(env.PROD_NAMESPACE)
      }
    }
  }
}

def deployHelm(String namespace) {
  withEnv(["NAMESPACE=${namespace}"]) {
    withCredentials([file(credentialsId: env.KUBECONFIG_CREDENTIALS_ID, variable: 'KUBECONFIG_FILE')]) {
      container('helm') {
        sh '''
        set -eu
        export KUBECONFIG="$KUBECONFIG_FILE"
        helm upgrade --install "$HELM_RELEASE" "$HELM_CHART_PATH" \
          --namespace "$NAMESPACE" --create-namespace \
          --set image.repository="$IMAGE_REPOSITORY" \
          --set image.tag="$IMAGE_TAG" \
          --wait --timeout 10m
        '''
      }
    }
  }
}
