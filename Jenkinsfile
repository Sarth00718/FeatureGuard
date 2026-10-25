/*
 * FeatureGuard CI/CD - declarative pipeline (Windows / Jenkins bat steps).
 * ------------------------------------------------------------
 * Runs on a Jenkins agent that can reach Docker, npm and Python on Windows.
 *
 * Credentials (create in Jenkins -> Credentials; nothing secret is stored here):
 *   featureguard-env   : "Secret file"  = your real .env   (used by the Deploy/rollback stages)
 *   featureguard-kube  : "Secret file"  = kubeconfig        (only needed when DEPLOY_TARGET=kubernetes)
 *
 * Stages: Checkout -> Install -> Python tests -> Frontend tests+build ->
 *         Train+quality gate -> Build images -> Smoke test -> Deploy (compose|kubernetes) -> Verify.
 * On failure the post block rolls the compose deployment back to the previous image tag.
 */

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
    }

    parameters {
        choice(name: 'DEPLOY_TARGET', choices: ['none', 'compose', 'kubernetes'], description: 'Where to deploy after all checks pass')
    }

    environment {
        IMAGE_TAG    = "${env.BUILD_NUMBER}"
        VENV         = "${env.WORKSPACE}\\.venv"
        PYTHON       = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
        DOCKER       = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe"
        COMPOSE      = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker-compose.exe"
        KUBECTL      = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\kubectl.exe"
    }

    stages {

        // Checkout Code
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // Install dependencies (Python venv + frontend npm)
        stage('Install dependencies') {
            steps {
                bat '''
@echo off
if exist "%VENV%\\Scripts\\python.exe" (
    echo [INFO] Virtual environment already exists at %VENV%. Reusing...
) else if exist "C:\\Users\\SARTH\\OneDrive\\Desktop\\MLOps\\FeatureGuard\\.venv\\Scripts\\python.exe" (
    echo [INFO] Initializing workspace venv from project folder...
    xcopy /E /I /Q /Y "C:\\Users\\SARTH\\OneDrive\\Desktop\\MLOps\\FeatureGuard\\.venv" "%VENV%"
) else (
    echo [INFO] Creating clean virtual environment...
    "%PYTHON%" -m venv "%VENV%"
)
"%VENV%\\Scripts\\python.exe" -m pip install --timeout=120 --retries=5 -q -r requirements.txt
'''
                dir('frontend') {
                    bat 'npm install --no-audit --no-fund --prefer-offline'
                }
            }
        }

        // Python tests (validation, drift, ML, API)
        stage('Python tests (validation, drift, ML, API)') {
            steps {
                bat '''
if not exist reports mkdir reports
"%VENV%\\Scripts\\python.exe" -m pytest -q --junitxml=reports/pytest.xml
'''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/pytest.xml'
                }
            }
        }

        // Frontend tests and build
        stage('Frontend tests and build') {
            steps {
                dir('frontend') {
                    bat 'npm test'
                    bat 'npm run build'
                }
            }
        }

        // Train model and quality gate
        // Fails the pipeline (exit 1) when the model is below the thresholds in params.yaml,
        // so a bad model can never reach the Docker build or the deployment.
        stage('Train model and quality gate') {
            steps {
                bat '"%VENV%\\Scripts\\python.exe" ml/download_data.py'
                bat '"%VENV%\\Scripts\\python.exe" -m ml.validate_data'
                bat '"%VENV%\\Scripts\\python.exe" -m ml.train'
            }
        }

        // Build Docker images
        stage('Build Docker images') {
            steps {
                bat '"%DOCKER%" build -t featureguard-backend:%IMAGE_TAG%  -t featureguard-backend:latest  -f backend/Dockerfile .'
                bat '"%DOCKER%" build -t featureguard-frontend:%IMAGE_TAG% -t featureguard-frontend:latest frontend'
                bat '"%DOCKER%" build -t featureguard-nginx:%IMAGE_TAG%    -t featureguard-nginx:latest    -f nginx/Dockerfile .'
            }
        }

        stage('Smoke test containers') {
            steps {
                bat '''
@echo off
if exist .env.ci del /f /q .env.ci
if exist .env.example (
    copy .env.example .env.ci >nul
) else (
    type nul > .env.ci
)
echo IMAGE_TAG=%IMAGE_TAG%>> .env.ci
echo HTTP_PORT=8081>> .env.ci
echo POSTGRES_USER=featureguard>> .env.ci
echo POSTGRES_PASSWORD=fg_smoke_pass>> .env.ci
echo POSTGRES_DB=featureguard>> .env.ci
'''
                // Write JSON payload to a file using Python - avoids Windows bat JSON escaping issues entirely
                bat '"%VENV%\\Scripts\\python.exe" scripts/write_smoke_payload.py'

                // Start smoke stack - only postgres, backend, frontend, nginx
                bat '"%COMPOSE%" -p fg-smoke --env-file .env.ci -f deployment/docker-compose.yml up -d --wait --wait-timeout 180 postgres backend frontend nginx'

                // Wait for backend readiness explicitly
                bat '"%DOCKER%" run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 --retry 15 --retry-delay 3 --retry-connrefused -fsS http://backend:8000/ready'

                // Test 1: backend health directly
                bat '"%DOCKER%" run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 -fsS http://backend:8000/health'

                // Test 2: prediction through nginx using file payload (avoids JSON quoting issues)
                bat '"%DOCKER%" run --rm --network fg-smoke_appnet -v "%WORKSPACE%/smoke_payload.json:/tmp/payload.json" curlimages/curl:8.10.1 -fsS -X POST -H "Content-Type: application/json" -d @/tmp/payload.json http://nginx/api/predict'
            }
            post {
                always {
                    bat '"%COMPOSE%" -p fg-smoke --env-file .env.ci -f deployment/docker-compose.yml down -v || exit 0'
                    bat 'if exist .env.ci del /f /q .env.ci || exit 0'
                    bat 'if exist smoke_payload.json del /f /q smoke_payload.json || exit 0'
                }
            }
        }

        // Deploy (compose)
        stage('Deploy (compose)') {
            when { expression { params.DEPLOY_TARGET == 'compose' } }
            steps {
                withCredentials([file(credentialsId: 'featureguard-env', variable: 'ENV_FILE')]) {
                    script {
                        // Safely check if previous container exists and get its image tag for rollback
                        def inspectStatus = bat(returnStatus: true, script: '@"%DOCKER%" inspect featureguard-prod-backend-1 >nul 2>&1')
                        if (inspectStatus == 0) {
                            def img = bat(returnStdout: true, script: '@"%DOCKER%" inspect --format "{{.Config.Image}}" featureguard-prod-backend-1').trim()
                            env.PREV_TAG = (img && img.contains(':')) ? img.tokenize(':').last() : ''
                        } else {
                            env.PREV_TAG = ''
                        }
                        echo "Previous running backend tag: ${env.PREV_TAG ?: 'none'}"
                    }
                    // Gracefully stop any existing dev compose stack that might be occupying host port 80
                    bat(returnStatus: true, script: '@"%COMPOSE%" -p deployment -f deployment/docker-compose.yml down >nul 2>&1')
                    // Deploy the verified images using --no-build
                    bat 'set "IMAGE_TAG=%IMAGE_TAG%" && "%COMPOSE%" -p featureguard-prod --env-file "%ENV_FILE%" -f deployment/docker-compose.yml up -d --no-build --wait --wait-timeout 180 postgres backend frontend nginx'
                }
            }
        }

        // Deploy (kubernetes)
        stage('Deploy (kubernetes)') {
            when { expression { params.DEPLOY_TARGET == 'kubernetes' } }
            steps {
                withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                    bat '"%KUBECTL%" apply --validate=false -f deployment/kubernetes/00-namespace-config.yaml'
                    bat '"%KUBECTL%" create configmap grafana-dashboards -n featureguard --from-file=monitoring/grafana/dashboards --dry-run=client -o yaml | "%KUBECTL%" apply --validate=false -f -'
                    bat '"%KUBECTL%" apply --validate=false -f deployment/kubernetes/'
                    bat '"%KUBECTL%" -n featureguard set image deployment/backend  backend=featureguard-backend:%IMAGE_TAG%'
                    bat '"%KUBECTL%" -n featureguard set image deployment/frontend frontend=featureguard-frontend:%IMAGE_TAG%'
                    bat '"%KUBECTL%" -n featureguard rollout status deployment/backend  --timeout=180s || ("%KUBECTL%" -n featureguard rollout undo deployment/backend  & exit 1)'
                    bat '"%KUBECTL%" -n featureguard rollout status deployment/frontend --timeout=120s || ("%KUBECTL%" -n featureguard rollout undo deployment/frontend & exit 1)'
                }
            }
        }

        // Verify service health
        stage('Verify service health') {
            when { expression { params.DEPLOY_TARGET != 'none' } }
            steps {
                script {
                    if (params.DEPLOY_TARGET == 'compose') {
                        bat '"%DOCKER%" run --rm --network featureguard-prod_appnet curlimages/curl:8.10.1 -fsS --retry 10 --retry-delay 3 --retry-connrefused http://nginx/api/ready'
                    } else {
                        withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                            bat '"%KUBECTL%" -n featureguard get pods && "%KUBECTL%" -n featureguard rollout status deployment/nginx --timeout=60s'
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline succeeded! FeatureGuard version ${IMAGE_TAG} has passed all gates and is running."
        }
        failure {
            echo "Build FAILED - Triggering automated rollback if applicable."
            script {
                // Compose rollback: bring the previous image tag back if the verify/deploy stage failed
                if (params.DEPLOY_TARGET == 'compose' && env.PREV_TAG?.trim() && env.PREV_TAG != env.IMAGE_TAG) {
                    echo "Rolling back compose deployment to previous tag: ${env.PREV_TAG}..."
                    withCredentials([file(credentialsId: 'featureguard-env', variable: 'ENV_FILE')]) {
                        bat 'set "IMAGE_TAG=%PREV_TAG%" && "%COMPOSE%" -p featureguard-prod --env-file "%ENV_FILE%" -f deployment/docker-compose.yml up -d --no-build postgres backend frontend nginx || exit 0'
                    }
                }
            }
        }
        always {
            bat 'if exist .env.ci del /f /q .env.ci || exit 0'
        }
    }
}
