# Patient Record Management System

A web-based patient record management system built with Flask for the COM7033 Secure Software Development module at Leeds Trinity University.

## Features

- **User Authentication** - Secure login with hashed passwords (SQLite)
- **Role-Based Access Control** - Admin and Clinician roles with different permissions
- **Patient Record CRUD** - Create, read, update, and archive patient records (MongoDB)
- **Audit Logging** - All patient actions are logged for accountability
- **CSRF Protection** - All forms protected against cross-site request forgery
- **Database Interconnection** - Patient records in MongoDB reference user IDs from SQLite

## Tech Stack

- **Backend:** Flask (Python)
- **User Database:** SQLite (authentication and user management)
- **Patient Database:** MongoDB (patient records and audit logs)
- **Frontend:** HTML templates with Jinja2, hand-written CSS
- **Containerisation:** Docker Compose (for MongoDB)

## Project Structure

```
patient-record-management-system/
├── app.py                    # All routes and application logic
├── requirements.txt          # Python dependencies
├── docker-compose.yml        # MongoDB container setup
├── README.md                 # This file
├── SECURITY.md               # STRIDE threat model and security notes
├── templates/
│   ├── base.html             # Shared layout (nav, flash messages)
│   ├── login.html            # Login form
│   ├── register.html         # Admin registers new users
│   ├── dashboard.html        # Role-based landing page
│   ├── patients.html         # Patient list table
│   ├── add_patient.html      # Add patient form
│   ├── view_patient.html     # View single patient
│   ├── edit_patient.html     # Edit patient form
│   ├── admin_users.html      # Admin: view/manage users
│   └── audit_log.html        # Admin: view audit log
├── static/
│   └── style.css             # All styling
└── tests/
    └── test_app.py           # Unit tests
```

## Installation

### Prerequisites

- Python 3.10+
- Docker and Docker Compose

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd patient-record-management-system
   ```

2. Start MongoDB using Docker:
   ```bash
   docker-compose up -d
   ```

3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and go to `http://localhost:5000`

### Default Admin Account

- **Username:** admin
- **Password:** admin123

## Running Tests

```bash
pytest tests/
```

## User Roles

| Role | Permissions |
|------|------------|
| **Admin** | Register users, manage users, view audit log, archive patients, view/edit patients |
| **Clinician** | Add patients, view patients, edit patients |

## Database Interconnection

The system uses two databases that work together:

- **SQLite** stores user accounts (id, username, hashed password, role)
- **MongoDB** stores patient records, each with a `created_by` field that references the SQLite user ID

This means every patient record is linked to the user who created it, connecting the two databases.
