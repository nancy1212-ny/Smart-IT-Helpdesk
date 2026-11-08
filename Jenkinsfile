pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out Smart IT Helpdesk'
            }
        }

        stage('Build') {
            steps {
                echo 'Building Docker image'
            }
        }

        stage('Test') {
            steps {
                echo 'Running application tests'
            }
        }

        stage('Complete') {
            steps {
                echo 'Pipeline completed successfully!'
            }
        }
    }
}