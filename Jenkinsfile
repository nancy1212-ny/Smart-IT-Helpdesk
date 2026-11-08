pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out Smart IT Helpdesk'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt pytest'
            }
        }

        stage('Test') {
            steps {
                bat 'python -m pytest -v'
            }
        }

        stage('Docker Build') {
            steps {
                bat 'docker build -t smart-it-helpdesk:latest .'
            }
        }

        stage('Complete') {
            steps {
                echo 'Build and tests completed successfully!'
            }
        }
    }
}