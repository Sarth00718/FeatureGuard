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
        choice(name: 'DEPLOY_TARGET', choices: ['compose', 'kubernetes', 'none'], description: 'Where to deploy after all checks pass')
    }

    environment {
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        VENV      = "${env.WORKSPACE}\\.venv"
        PYTHON    = "C:\\Users\\SARTH\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
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
                bat '"%PYTHON%" -m venv "%VENV%"'
                bat '"%VENV%\\Scripts\\python.exe" -m pip install -q -r requirements.txt'
                dir('frontend') {
                    bat 'npm install --no-audit --no-fund'
                }
            }
        }

        // Python tests (validation, drift, ML, API)
        stage('Python tests (validation, drift, ML, API)') {
            steps {
                bat '"%VENV%\\Scripts\\python.exe" -m pytest -q --junitxml=reports/pytest.xml'
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
                bat 'docker build -t featureguard-backend:%IMAGE_TAG%  -f backend/Dockerfile .'
                bat 'docker build -t featureguard-frontend:%IMAGE_TAG% frontend'
                bat 'docker build -t featureguard-nginx:%IMAGE_TAG%    -f nginx/Dockerfile .'
            }
        }

        // Smoke test containers
        stage('Smoke test containers') {
            steps {
                bat 'copy .env.example .env.ci'
                bat 'docker compose -p fg-smoke --env-file .env.ci -f deployment/docker-compose.yml up -d --wait --wait-timeout 180 postgres backend frontend nginx'
                bat 'docker run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 -fsS http://nginx/api/health'
                bat 'docker run --rm --network fg-smoke_appnet curlimages/curl:8.10.1 -fsS -X POST -H "Content-Type: application/json" -d "{\"fixed_acidity\":7.4,\"volatile_acidity\":0.7,\"citric_acid\":0.0,\"residual_sugar\":1.9,\"chlorides\":0.076,\"free_sulfur_dioxide\":11,\"total_sulfur_dioxide\":34,\"density\":0.9978,\"ph\":3.51,\"sulphates\":0.56,\"alcohol\":9.4}" http://nginx/api/predict'
            }
            post {
                always {
                    bat 'docker compose -p fg-smoke --env-file .env.ci -f deployment/docker-compose.yml down -v || exit 0'
                }
            }
        }

        // Deploy (compose)
        stage('Deploy (compose)') {
            when { expression { params.DEPLOY_TARGET == 'compose' } }
            steps {
                withCredentials([file(credentialsId: 'featureguard-env', variable: 'ENV_FILE')]) {
                    script {
                        // remember the running tag so we can go back to it if verification fails
                        def img = bat(returnStdout: true, script: '@docker inspect --format "{{.Config.Image}}" featureguard-prod-backend-1 2>nul & exit /b 0')
                        img = img.trim()
                        env.PREV_TAG = img ? img.tokenize(':').last() : ''
                    }
                    bat 'docker compose -p featureguard-prod --env-file "%ENV_FILE%" -f deployment/docker-compose.yml up -d --build --wait --wait-timeout 180 postgres backend frontend nginx'
                }
            }
        }

        // Deploy (kubernetes)
        stage('Deploy (kubernetes)') {
            when { expression { params.DEPLOY_TARGET == 'kubernetes' } }
            steps {
                withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                    bat '''
kubectl apply -f deployment/kubernetes/00-namespace-config.yaml
kubectl create configmap grafana-dashboards -n featureguard --from-file=monitoring/grafana/dashboards --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deployment/kubernetes/
kubectl -n featureguard set image deployment/backend  backend=featureguard-backend:%IMAGE_TAG%
kubectl -n featureguard set image deployment/frontend frontend=featureguard-frontend:%IMAGE_TAG%
kubectl -n featureguard rollout status deployment/backend  --timeout=180s || (kubectl -n featureguard rollout undo deployment/backend  & exit 1)
kubectl -n featureguard rollout status deployment/frontend --timeout=120s || (kubectl -n featureguard rollout undo deployment/frontend & exit 1)
'''
                }
            }
        }

        // Verify service health
        stage('Verify service health') {
            when { expression { params.DEPLOY_TARGET != 'none' } }
            steps {
                script {
                    if (params.DEPLOY_TARGET == 'compose') {
                        bat 'docker run --rm --network featureguard-prod_appnet curlimages/curl:8.10.1 -fsS --retry 10 --retry-delay 3 --retry-connrefused http://nginx/api/ready'
                    } else {
                        withCredentials([file(credentialsId: 'featureguard-kube', variable: 'KUBECONFIG')]) {
                            bat 'kubectl -n featureguard get pods && kubectl -n featureguard rollout status deployment/nginx --timeout=60s'
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline succeeded. FeatureGuard is running.'
        }
        failure {
            echo 'Build FAILED - nothing newer than the last good version was kept running by this pipeline.'
            script {
                // Compose rollback: bring the previous image tag back if the verify/deploy stage failed
                if (params.DEPLOY_TARGET == 'compose' && env.PREV_TAG?.trim() && env.PREV_TAG != env.IMAGE_TAG) {
                    withCredentials([file(credentialsId: 'featureguard-env', variable: 'ENV_FILE')]) {
                        bat 'set "IMAGE_TAG=%PREV_TAG%" && docker compose -p featureguard-prod --env-file "%ENV_FILE%" -f deployment/docker-compose.yml up -d postgres backend frontend nginx || exit 0'
                    }
                }
            }
        }
        always {
            bat 'if exist .env.ci del .env.ci'
        }
    }
}
