# Credit Approval System

An assignment for the Alemeno Backend Internship.
Made By: Kartik Sharma

---

This is a backend system for a credit approval process, built with Django, Django Rest Framework, PostgreSQL, and Celery. The entire application is containerized using Docker.

## Prerequisites

- Docker
- Docker Compose

## How to Run

1.  **Clone the repository:**
    ```sh
    git clone <your-repository-url>
    cd <your-project-folder>
    ```

2.  **Build and start the containers:**
    ```sh
    docker-compose up --build
    ```
    This will start all the required services (web server, database, celery worker, and redis).

3.  **Run Database Migrations (First time only):**
    In a new terminal, run the following command to set up the database schema:
    ```sh
    docker-compose run --rm web python manage.py migrate
    ```

4.  **Ingest Initial Data (First time only):**
    To populate the database with the initial data from the provided Excel files, run this command:
    ```sh
    docker-compose exec web python manage.py ingest_data
    ```
    You can check the logs of the `credit_celery` container in the first terminal to see the progress.

## API Endpoints

The API is available at `http://localhost:8000/api/`.

- `POST /api/register/`
- `POST /api/check-eligibility/`
- `POST /api/create-loan/`
- `GET /api/view-loan/<loan_id>/`
- `GET /api/view-loans/<customer_id>/`