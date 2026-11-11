# Smart IT Helpdesk & Ticket Management System

## Project Overview
A web-based IT Helpdesk system that allows employees to submit IT support tickets and enables administrators and technicians to manage, assign, track, and resolve them.

## Features
- Role-based login: Employee, Admin, and Technician
- Create and submit support tickets
- Assign tickets to technicians
- Update ticket status
- Add comments and replies
- View ticket activity history
- SLA deadline tracking and overdue alerts
- Search and filter tickets
- Duplicate active ticket detection
- Admin analytics dashboard

## Technology Stack
- **Frontend:** HTML, CSS, Bootstrap, JavaScript
- **Backend:** Python, Flask
- **Database:** PostgreSQL
- **Database Driver:** Psycopg
- **Testing:** Pytest
- **Version Control:** Git and GitHub
- **CI/CD:** Jenkins
- **Containerization:** Docker
- **Deployment:** Render
- **Cloud Database:** Neon PostgreSQL

## Demo Application
https://smart-it-helpdesk-rd1i.onrender.com

## Demo Login Accounts

| Role | Email |
|---|---|
| Employee | john@gmail.com |
| Admin | james@gmail.com |
| Technician | daniel@gmail.com |

*Demo passwords should be shared separately and changed before production use.*

## Run Locally

1. Clone the repository:

```bash
git clone https://github.com/nancy1212-ny/Smart-IT-Helpdesk.git
```

2. Open the project folder:

```bash
cd Smart-IT-Helpdesk
```

3. Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Configure database environment variables in a `.env` file.

6. Start the application:

```bash
python app.py
```

7. Open `http://127.0.0.1:5000` in your browser.

## Run Tests

```bash
pytest -v
```

## Docker

Build the image:

```bash
docker build -t smart-it-helpdesk .
```

Run the container:

```bash
docker run -p 5000:5000 --env-file .env smart-it-helpdesk
```

## CI/CD
Jenkins pipeline automates:
- GitHub source code checkout
- Dependency installation
- Automated testing with Pytest
- Docker image building

## Learning Outcomes
This project demonstrates practical knowledge of Python web development, REST-based application concepts, relational database management, authentication, role-based access control, software testing, Docker, CI/CD, and cloud deployment.

## Repository
https://github.com/nancy1212-ny/Smart-IT-Helpdesk