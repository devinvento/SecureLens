# SecureLens Web PenTester - How It Works

SecureLens is a modern web penetration testing suite built with FastAPI, PostgreSQL, Redis, and Celery. It is designed to be easily deployable using Docker.

## Architecture Overview

The system consists of several components working together:

1.  **Web Server (FastAPI)**: The main application that serves the API and the static frontend.
2.  **Database (PostgreSQL)**: Stores user data, scan targets, and results.
3.  **Task Queue (Redis)**: Handles communication between the web server and background workers.
4.  **Worker (Celery)**: Executes long-running penetration testing tasks (like Nmap scans) asynchronously.

## Setup and Initialization Flow

When you run `docker-compose up`, the following steps occur:

### 1. Database Readiness
The [entrypoint.sh](file:///var/www/html/SecureLens/entrypoint.sh) script starts first. It waits for the PostgreSQL database to be ready by attempting to connect to it using `psycopg2`.

### 2. Schema Creation & Initialization
Once the database is ready, the script runs:
```bash
python -m app.db.init_db
```
This command executes [app/db/init_db.py](file:///var/www/html/SecureLens/app/db/init_db.py), which:
- Uses SQLAlchemy to create all tables (`Base.metadata.create_all`).
- Creates a default admin user (`admin@securelens.local`).
- Seeds the database with default lab targets (DVWA, Juice Shop, etc.).

### 3. Application Startup
Finally, the web application starts using Uvicorn on port `4567`.

## Troubleshooting Common Errors

### `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "users" does not exist`

**Why this happens:**
This error occurs when the database schema has not been initialized. SQLAlchemy is trying to query the `users` table, but the table hasn't been created in the underlying PostgreSQL database yet.

**How to fix:**
This is usually handled automatically by the [entrypoint.sh](file:///var/www/html/SecureLens/entrypoint.sh) script during the first run. If you see this error:

1.  **Check Logs**: Look at the logs for the `web` and `db` containers.
    ```bash
    docker-compose logs web
    ```
2.  **Ensure Initialization Ran**: If the initialization script failed or was skipped, you can run it manually inside the container:
    ```bash
    docker-compose exec web python -m app.db.init_db
    ```
### `GET http://localhost:4567/js/app.js 404 (Not Found)`

**Why this happens:**
The script was previously referenced at `js/app.js`, but it is actually located within the `assets` folder at `assets/js/app.js`.

**How to fix:**
This has been fixed in all core HTML files (`index.html`, `dashboard.html`, `scans.html`, `lab.html`). If you create new pages, ensures you reference the app script correctly:
```html
<script src="assets/js/app.js"></script>
```

## Development & Usage

- **Static Files**: The frontend is served from the `static/` directory.
- **API Documentation**: Once running, access the interactive API docs at `http://localhost:4567/docs`.
- **Worker Logs**: Monitor background task execution with `docker-compose logs worker`.
