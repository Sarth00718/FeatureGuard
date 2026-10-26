pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
    }

    parameters {
        choice(
            name: 'DEPLOY_TARGET',
            choices: ['none', 'compose', 'kubernetes'],
            description: 'Deployment target after tests pass.'
        )
    }

    environment {
        IMAGE_TAG = "${BUILD_NUMBER}"
        VENV = "${WORKSPACE}\\.venv"

        // Update these paths if Python or Docker is installed elsewhere.
        PYTHON = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
        DOCKER = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe"
        COMPOSE = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker-compose.exe"
        KUBECTL = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\kubectl.exe"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install dependencies') {
            steps {
                bat '''
@echo off
if not exist "%PYTHON%" (
    echo Python not found: "%PYTHON%"
    echo Update PYTHON in the Jenkinsfile or configure the Jenkins service PATH.
    exit /b 1
)

if not exist "%VENV%\\Scripts\\python.exe" (
    "%PYTHON%" -m venv "%VENV%"
    if errorlevel 1 exit /b 1
)

"%VENV%\\Scripts\\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%VENV%\\Scripts\\python.exe" -m pip install --timeout=120 --retries=5 -r requirements.txt
'''
                dir('frontend') {
                    bat 'npm ci --no-audit --no-fund'
                }
            }
        }

        stage('Python tests') {
            steps {
                bat '''
if not exist reports mkdir reports
"%VENV%\\Scripts\\python.exe" -m pytest -q --junitxml=reports\\pytest.xml
'''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/pytest.xml'
                }
            }
        }

        stage('Frontend tests and build') {
            steps {
                dir('frontend') {
                    bat 'npm test'
                    bat 'npm run build'
                }
            }
        }

        stage('Train model and validate quality') {
            steps {
                bat '"%VENV%\\Scripts\\python.exe" ml\\download_data.py'
                bat '"%VENV%\\Scripts\\python.exe" -m ml.validate_data'
                bat '"%VENV%\\Scripts\\python.exe" -m ml.train'
            }
        }

        stage('Build Docker images') {
            steps {
                bat '''
"%DOCKER%" build -t featureguard-backend:%IMAGE_TAG% -t featureguard-backend:latest -f backend\\Dockerfile .
if errorlevel 1 exit /b 1

"%DOCKER%" build -t featureguard-frontend:%IMAGE_TAG% -t featureguard-frontend:latest frontend
if errorlevel 1 exit /b 1

"%DOCKER%" build -t featureguard-nginx:%IMAGE_TAG% -t featureguard-nginx:latest -f nginx\\Dockerfile .
'''
            }
        }

        stage('Smoke test containers') {
            steps {
                bat '''
@echo off
(
    echo IMAGE_TAG=%IMAGE_TAG%
    echo HTTP_PORT=18081
    echo PROMETHEUS_PORT=19091
    echo POSTGRES_USER=featureguard
    echo POSTGRES_PASSWORD=fg_smoke_local
    echo POSTGRES_DB=featureguard
    echo GRAFANA_PASSWORD=fg_smoke_local
) > .env.ci
'''
                bat '"%COMPOSE%" -p fg-smoke --env-file .env.ci -f deployment\\docker-compose.yml up -d --wait --wait-timeout 180 postgres backend frontend nginx'
                bat '"%DOCKER%" run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 -fsS --retry 10 --retry-delay 2 --retry-connrefused http://backend:8000/health'
                bat '"%DOCKER%" run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 -fsS --retry 10 --retry-delay 2 --retry-connrefused http://nginx/api/health'
            }
            post {
                always {
                    bat '"%COMPOSE%" -p fg-smoke --env-file .env.ci -f deployment\\docker-compose.yml down -v || exit 0'
                    bat 'if exist .env.ci del /f /q .env.ci || exit 0'
                }
            }
        }

        stage('Deploy with Docker Compose') {
            when {
                expression { params.DEPLOY_TARGET == 'compose' }
            }
            steps {
                withCredentials([file(credentialsId: 'featureguard-env', variable: 'ENV_FILE')]) {
                    bat '"%COMPOSE%" -p featureguard-prod --env-file "%ENV_FILE%" -f deployment\\docker-compose.yml up -d --no-build --wait --wait-timeout 180 postgres backend frontend nginx'
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { params.DEPLOY_TARGET == 'kubernetes' }
            }
            steps {
                withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\00-namespace-config.yaml'
                    bat '"%KUBECTL%" create configmap grafana-dashboards -n featureguard --from-file=monitoring\\grafana\\dashboards --dry-run=client -o yaml | "%KUBECTL%" apply -f -'
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\10-postgres.yaml'
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\20-backend.yaml'
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\30-frontend.yaml'
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\40-nginx.yaml'
                    bat '"%KUBECTL%" apply -f deployment\\kubernetes\\50-monitoring.yaml'
                    bat '"%KUBECTL%" -n featureguard set image deployment/backend backend=featureguard-backend:%IMAGE_TAG%'
                    bat '"%KUBECTL%" -n featureguard set image deployment/frontend frontend=featureguard-frontend:%IMAGE_TAG%'
                    bat '"%KUBECTL%" -n featureguard rollout status deployment/backend --timeout=180s'
                    bat '"%KUBECTL%" -n featureguard rollout status deployment/frontend --timeout=120s'
                }
            }
        }

        stage('Verify deployment') {
            when {
                expression { params.DEPLOY_TARGET != 'none' }
            }
            steps {
                script {
                    if (params.DEPLOY_TARGET == 'compose') {
                        bat '"%DOCKER%" run --rm --network featureguard-prod_appnet curlimages/curl:8.10.1 -fsS --retry 10 --retry-delay 3 --retry-connrefused http://nginx/api/ready'
                    } else {
                        withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                            bat '"%KUBECTL%" -n featureguard get pods'
                            bat '"%KUBECTL%" -n featureguard rollout status deployment/nginx --timeout=60s'
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "FeatureGuard build ${IMAGE_TAG} completed successfully."
        }
        failure {
            echo 'Pipeline failed. Check the first failed stage in the console output.'
        }
        always {
            bat 'if exist .env.ci del /f /q .env.ci'
        }
    }
}
