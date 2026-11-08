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
                bat '"C:\\Users\\nancy\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" -m pip install -r requirements.txt pytest'
            }
        }

        stage('Test') {
            steps {
                bat '"C:\\Users\\nancy\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" -m pytest -v'
            }
        }

        stage('Docker Build') {
            steps {
                bat '"C:\\Users\\nancy\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe" build -t smart-it-helpdesk:latest .'
            }
        }

        stage('Complete') {
            steps {
                echo 'Build and tests completed successfully!'
            }
        }
    }
}